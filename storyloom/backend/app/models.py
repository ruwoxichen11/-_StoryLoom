"""故事织机 - 领域数据模型（Pydantic）

一部"作品（Work）"包含：故事基因、角色阵容、经纬大纲、章节、研讨记录。
全部以 JSON 文件落盘（见 db.py）。
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------- 故事基因（Stage 1） ----------------
class StoryGene(BaseModel):
    raw_input: str = ""
    genre: str = ""
    mood: str = ""
    core_tension: str = ""
    world_premise: str = ""
    keywords: List[str] = Field(default_factory=list)
    scale_hint: str = ""


# ---------------- 角色（Stage 2） ----------------
class Character(BaseModel):
    id: str = ""
    name: str = ""
    archetype: str = ""
    look: str = ""
    temper: str = ""
    drive: str = ""
    flaw: str = ""
    tagline: str = ""
    secret: str = ""
    accent: str = "#4f7cff"


# ---------------- 大纲（Stage 3） ----------------
class Beat(BaseModel):
    order: int = 0
    title: str = ""
    summary: str = ""
    kind: str = "rising"  # opening/rising/turn/climax/ending
    cast: List[str] = Field(default_factory=list)


class Thread(BaseModel):
    name: str = ""
    summary: str = ""
    accent: str = "#2db3a6"


class Outline(BaseModel):
    beats: List[Beat] = Field(default_factory=list)
    threads: List[Thread] = Field(default_factory=list)
    locked: bool = False


# ---------------- 章节（Stage 4 / 5） ----------------
class StageBlock(BaseModel):
    """圆桌戏台产生的一段记录"""
    kind: str = "line"        # scene(旁白) / line(角色发言)
    speaker: str = ""         # 角色名或"旁白"
    text: str = ""
    trace: List[dict] = Field(default_factory=list)  # ReAct 推理链


class Chapter(BaseModel):
    num: int = 1
    title: str = ""
    status: str = "todo"      # todo / drafting / done
    cast: List[str] = Field(default_factory=list)
    brief: str = ""           # 本章目标/微纲
    words: int = 0
    blocks: List[StageBlock] = Field(default_factory=list)
    manuscript: str = ""      # 誊抄后的正文
    chapter_setting: str = ""


# ---------------- 作品 ----------------
class Work(BaseModel):
    id: str = ""
    title: str = "未命名作品"
    synopsis: str = ""
    stage: int = 1            # 当前进行到第几个阶段
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)

    gene: StoryGene = Field(default_factory=StoryGene)
    characters: List[Character] = Field(default_factory=list)
    outline: Outline = Field(default_factory=Outline)
    chapters: List[Chapter] = Field(default_factory=list)
