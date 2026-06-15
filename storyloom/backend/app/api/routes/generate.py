"""AI 生成路由（Stage 1-4 + 润色/审稿），均以 SSE 流式返回"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core import bootstrap  # noqa: F401
from app import db
from app.models import StoryGene, Character, Beat, Thread
from app.schemas import InspirationReq
from app.services.lore_service import build_work_setting, reindex_lore
from agent import MuseAgent, CastmakerAgent, LoomPlannerAgent, AuditorAgent
from utils.textkit import extract_json, slugify

router = APIRouter()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ---------------- Stage 1：灵感 -> 故事基因 ----------------
@router.post("/{work_id}/gene/extract")
async def extract_gene(work_id: str, req: InspirationReq):
    work = db.get_work(work_id)
    if not work:
        raise HTTPException(404, "作品不存在")

    async def gen():
        agent = MuseAgent()
        buf = ""
        async for piece in agent.stream(
            user_message=f"灵感原文：\n{req.text}", temperature=0.7, max_tokens=1200
        ):
            buf += piece
            yield _sse("delta", {"text": piece})
        parsed = extract_json(buf) or {}
        gene = StoryGene(raw_input=req.text, **{
            k: v for k, v in parsed.items() if k in StoryGene.model_fields
        })
        w = db.get_work(work_id)
        w.gene = gene
        w.stage = max(w.stage, 2)
        db.save_work(w)
        yield _sse("done", {"gene": gene.model_dump()})

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------------- Stage 2：基因 -> 角色阵容 ----------------
@router.post("/{work_id}/cast/generate")
async def generate_cast(work_id: str):
    work = db.get_work(work_id)
    if not work:
        raise HTTPException(404, "作品不存在")

    async def gen():
        agent = CastmakerAgent(work_setting=build_work_setting(work))
        g = work.gene
        prompt = (
            f"故事基因：题材={g.genre}，基调={g.mood}，核心矛盾={g.core_tension}，"
            f"世界观={g.world_premise}，关键词={'、'.join(g.keywords)}。请设计角色阵容。"
        )
        buf = ""
        async for piece in agent.stream(prompt, temperature=0.85, max_tokens=1800):
            buf += piece
            yield _sse("delta", {"text": piece})
        parsed = extract_json(buf) or {}
        chars = []
        for c in parsed.get("cast", []):
            c["id"] = slugify(c.get("name", "role"))
            chars.append(Character.model_validate({
                k: v for k, v in c.items() if k in Character.model_fields
            }))
        w = db.get_work(work_id)
        w.characters = chars
        w.stage = max(w.stage, 3)
        db.save_work(w)
        reindex_lore(w)
        yield _sse("done", {"characters": [c.model_dump() for c in chars]})

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------------- Stage 3：角色 -> 大纲 ----------------
@router.post("/{work_id}/outline/generate")
async def generate_outline(work_id: str):
    work = db.get_work(work_id)
    if not work:
        raise HTTPException(404, "作品不存在")

    async def gen():
        agent = LoomPlannerAgent(work_setting=build_work_setting(work))
        names = "、".join(c.name for c in work.characters)
        prompt = f"角色阵容：{names}。请据此规划主线节点与支线。"
        buf = ""
        async for piece in agent.stream(prompt, temperature=0.75, max_tokens=2400):
            buf += piece
            yield _sse("delta", {"text": piece})
        parsed = extract_json(buf) or {}
        beats = [Beat.model_validate({k: v for k, v in b.items() if k in Beat.model_fields})
                 for b in parsed.get("beats", [])]
        threads = [Thread.model_validate({k: v for k, v in t.items() if k in Thread.model_fields})
                   for t in parsed.get("threads", [])]
        w = db.get_work(work_id)
        w.outline.beats = beats
        w.outline.threads = threads
        w.stage = max(w.stage, 3)
        db.save_work(w)
        reindex_lore(w)
        yield _sse("done", {"outline": w.outline.model_dump()})

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------------- Stage 4：章节微纲 ----------------
@router.post("/{work_id}/chapters/{num}/brief/generate")
async def generate_chapter_brief(work_id: str, num: int):
    work = db.get_work(work_id)
    if not work:
        raise HTTPException(404, "作品不存在")
    chapter = next((c for c in work.chapters if c.num == num), None)
    if not chapter:
        raise HTTPException(404, "章节不存在")

    async def gen():
        agent = LoomPlannerAgent(work_setting=build_work_setting(work))
        prompt = (
            f"为第{num}章《{chapter.title}》撰写一段创作微纲（150字内），"
            f"说明本章目标、出场角色（{('、'.join(chapter.cast)) or '自定'}）、"
            f"核心冲突与需要埋下或回收的伏笔。直接输出文本。"
        )
        buf = ""
        async for piece in agent.stream(prompt, temperature=0.7, max_tokens=600):
            buf += piece
            yield _sse("delta", {"text": piece})
        w = db.get_work(work_id)
        for ch in w.chapters:
            if ch.num == num:
                ch.brief = buf.strip()
        w.stage = max(w.stage, 4)
        db.save_work(w)
        yield _sse("done", {"brief": buf.strip()})

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------------- Stage 6：一致性审稿 ----------------
@router.post("/{work_id}/audit")
async def audit(work_id: str):
    work = db.get_work(work_id)
    if not work:
        raise HTTPException(404, "作品不存在")

    async def gen():
        agent = AuditorAgent(work_setting=build_work_setting(work))
        manuscripts = "\n\n".join(
            f"第{c.num}章《{c.title}》\n{c.manuscript}" for c in work.chapters if c.manuscript
        ) or "（暂无成稿章节）"
        buf = ""
        async for piece in agent.stream(
            f"请复核以下正文：\n{manuscripts[:6000]}", temperature=0.4, max_tokens=2000
        ):
            buf += piece
            yield _sse("delta", {"text": piece})
        yield _sse("done", {"report": extract_json(buf) or {"verdict": buf.strip()[:200]}})

    return StreamingResponse(gen(), media_type="text/event-stream")
