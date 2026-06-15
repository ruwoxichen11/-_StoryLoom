"""故事织机 - 圆桌戏台 WebSocket（Stage 5 核心）

调度循环：
  Showrunner 下达一条 JSON 指令（cue/volley/scene/wrap）
    -> 对应角色 ActorAgent 走 ReAct（Thought->Action(工具)->Observation->发言）
    -> 实时把发言与推理链推给前端
    -> 字数预算控制；可暂停（真正停止下一次调用）/恢复/强制结束
  结束 -> 交 Scribe 誊抄成正文，写回章节
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core import bootstrap  # noqa: F401
from app import db
from app.models import StageBlock
from app.services.lore_service import build_work_setting
from agent import ShowrunnerAgent, ScribeAgent, build_actor
from utils.textkit import count_cn_words, extract_json

router = APIRouter()

_sessions: dict[str, "RoundtableSession"] = {}


class RoundtableSession:
    def __init__(self, work_id: str, chapter_num: int) -> None:
        self.work_id = work_id
        self.chapter_num = chapter_num
        self.budget = 0
        self.ceiling = 0
        self.words = 0
        self.running = False
        self.paused = False
        self.phase = "idle"
        self.blocks: list[dict] = []
        self.actors: dict = {}
        self.showrunner = None
        self.work_setting = ""
        self.chapter_setting = ""

    # ---- 上下文工具 ----
    def recent_scene(self, n: int = 6) -> str:
        parts = []
        for b in self.blocks[-n:]:
            if b["kind"] == "scene":
                parts.append(f"【场景】{b['text']}")
            else:
                parts.append(f"{b['speaker']}：{b['text']}")
        return "\n".join(parts)

    def raw_transcript(self) -> str:
        parts = []
        for b in self.blocks:
            if b["kind"] == "scene":
                parts.append(b["text"])
            else:
                parts.append(f"{b['speaker']}：{b['text']}")
        return "\n\n".join(parts)

    def _setup_agents(self) -> list[str]:
        work = db.get_work(self.work_id)
        chapter = next((c for c in work.chapters if c.num == self.chapter_num), None)
        self.work_setting = build_work_setting(work)
        self.chapter_setting = (chapter.brief if chapter else "")

        self.showrunner = ShowrunnerAgent(
            work_setting=self.work_setting, chapter_setting=self.chapter_setting
        )
        names = []
        for c in work.characters:
            actor = build_actor(
                character=c.model_dump(),
                work_id=self.work_id,
                recent_scene_getter=self.recent_scene,
                work_setting=self.work_setting,
                chapter_setting=self.chapter_setting,
            )
            self.actors[c.name] = actor
            names.append(c.name)
        return names

    # ---- 主循环 ----
    async def loop(self, ws: WebSocket):
        names = self._setup_agents()
        if not names:
            await _send(ws, {"type": "error", "message": "尚无角色，请先在选角阶段生成角色"})
            return

        work = db.get_work(self.work_id)
        chapter = next((c for c in work.chapters if c.num == self.chapter_num), None)
        title = chapter.title if chapter else f"第{self.chapter_num}章"

        self.phase = "performing"
        await _send(ws, {"type": "phase", "phase": "performing"})

        directive = None
        guard = 0
        while self.running and self.words < self.ceiling and guard < 60:
            guard += 1
            if self.paused:
                await asyncio.sleep(0.3)
                continue

            if directive is None:
                directive = await self._ask_showrunner(ws, names, title)
            if directive is None:
                await asyncio.sleep(0.4)
                continue

            act = directive.get("act", "cue")
            if act == "wrap":
                await _send(ws, {"type": "showrunner",
                                 "text": f"〔收束〕{directive.get('why', '本章告一段落')}"})
                break
            elif act == "scene":
                await self._narrate(ws, directive.get("note", ""))
            elif act == "cue":
                who = directive.get("who", names[0])
                who = who if who in self.actors else names[0]
                await self._actor_turn(ws, who, directive.get("note", ""))
            elif act == "volley":
                whos = [w for w in directive.get("who", []) if w in self.actors] or names[:2]
                for _ in range(int(directive.get("rounds", 1))):
                    for who in whos:
                        if not self.running or self.words >= self.ceiling or self.paused:
                            break
                        await self._actor_turn(ws, who, directive.get("note", ""))

            directive = None
            await _send(ws, {"type": "progress", "words": self.words,
                             "budget": self.budget, "ceiling": self.ceiling})
            await asyncio.sleep(0.25)

        self.phase = "done"
        self.running = False
        await _send(ws, {"type": "phase", "phase": "done"})
        await _send(ws, {"type": "ended", "transcript": self.raw_transcript(),
                         "words": self.words})

    async def _ask_showrunner(self, ws: WebSocket, names: list[str], title: str) -> dict | None:
        status = (f"⚠️ 已达预算（{self.words}/{self.budget}），请尽快 wrap"
                  if self.words >= self.budget else f"字数 {self.words}/{self.budget}")
        prompt = (
            f"本章：{title}\n可用角色：{'、'.join(names)}\n{status}\n\n"
            f"最近场景：\n{self.recent_scene()}\n\n请下达下一条指令 JSON。"
        )
        try:
            result = await self.showrunner.run(prompt, temperature=0.6, max_tokens=300)
            return extract_json(result) or {"act": "cue", "who": names[0], "note": ""}
        except Exception:  # noqa: BLE001
            return {"act": "cue", "who": names[0], "note": ""}

    async def _actor_turn(self, ws: WebSocket, name: str, note: str):
        actor = self.actors.get(name)
        if not actor:
            return
        await _send(ws, {"type": "thinking", "speaker": name})
        result = await actor.perform(scene_brief=self.recent_scene() or "（开场）", note=note)
        text = result["text"].strip()
        if text.endswith(("Over", "over")):
            text = text[:-4].strip()
        self.words += count_cn_words(text)
        block = {"kind": "line", "speaker": name, "text": text, "trace": result["trace"]}
        self.blocks.append(block)
        await _send(ws, {"type": "line", "speaker": name, "text": text,
                         "trace": result["trace"], "words": self.words})

    async def _narrate(self, ws: WebSocket, note: str):
        prompt = f"为当前场景写一段不超过90字的环境/转场旁白。\n上下文：\n{self.recent_scene()}\n要点：{note}"
        try:
            text = (await self.showrunner.run(prompt, temperature=0.8, max_tokens=240)).strip()
        except Exception:  # noqa: BLE001
            return
        if "{" in text:
            text = text.split("{")[0].strip()
        self.words += count_cn_words(text)
        self.blocks.append({"kind": "scene", "speaker": "旁白", "text": text, "trace": []})
        await _send(ws, {"type": "showrunner", "text": text, "words": self.words})

    async def polish(self, ws: WebSocket, raw: str):
        scribe = ScribeAgent(work_setting=self.work_setting, chapter_setting=self.chapter_setting)
        await _send(ws, {"type": "phase", "phase": "polishing"})
        buf = ""
        async for piece in scribe.stream(
            f"原始研讨记录：\n{raw}", temperature=0.7, max_tokens=4096
        ):
            buf += piece
            await _send(ws, {"type": "polish_delta", "text": piece})
        work = db.get_work(self.work_id)
        for ch in work.chapters:
            if ch.num == self.chapter_num:
                ch.manuscript = buf
                ch.words = count_cn_words(buf)
                ch.status = "done"
                ch.blocks = [StageBlock.model_validate(b) for b in self.blocks]
        db.save_work(work)
        await _send(ws, {"type": "polished", "manuscript": buf})


async def _send(ws: WebSocket, data: dict):
    try:
        await ws.send_text(json.dumps(data, ensure_ascii=False))
    except Exception:  # noqa: BLE001
        pass


@router.websocket("/ws/roundtable/{work_id}/{chapter_num}")
async def roundtable_ws(ws: WebSocket, work_id: str, chapter_num: int):
    await ws.accept()
    key = f"{work_id}:{chapter_num}"
    session = _sessions.setdefault(key, RoundtableSession(work_id, chapter_num))
    await _send(ws, {"type": "ready"})

    try:
        while True:
            data = json.loads(await ws.receive_text())
            action = data.get("action")

            if action == "start":
                session.budget = int(data.get("budget", 2500))
                session.ceiling = int(data.get("ceiling", 3500))
                session.words = 0
                session.blocks = []
                session.actors = {}
                session.running = True
                session.paused = False
                asyncio.create_task(session.loop(ws))
            elif action == "pause":
                session.paused = True
                await _send(ws, {"type": "paused"})
            elif action == "resume":
                session.paused = False
                await _send(ws, {"type": "resumed", "phase": session.phase})
            elif action == "stop":
                session.running = False
                await _send(ws, {"type": "ended", "transcript": session.raw_transcript(),
                                 "words": session.words, "reason": "manual"})
            elif action == "polish":
                await session.polish(ws, data.get("text", "") or session.raw_transcript())

    except WebSocketDisconnect:
        session.running = False
    except Exception as exc:  # noqa: BLE001
        session.running = False
        await _send(ws, {"type": "error", "message": str(exc)})
