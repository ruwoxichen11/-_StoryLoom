"""作品 CRUD 与各阶段数据编辑路由"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core import bootstrap  # noqa: F401
from app import db
from app.models import Character, Beat, Thread, Chapter
from app.schemas import (
    CreateWorkReq, GeneEditReq, CharacterEditReq, OutlineEditReq, ChapterBriefReq,
)
from utils.textkit import slugify

router = APIRouter()


@router.get("")
def list_works():
    return {"works": db.list_works()}


@router.post("")
def create_work(req: CreateWorkReq):
    work = db.create_work(req.title, req.synopsis)
    return work.model_dump()


@router.get("/{work_id}")
def get_work(work_id: str):
    work = db.get_work(work_id)
    if not work:
        raise HTTPException(404, "作品不存在")
    return work.model_dump()


@router.delete("/{work_id}")
def delete_work(work_id: str):
    ok = db.delete_work(work_id)
    if not ok:
        raise HTTPException(404, "作品不存在")
    return {"deleted": True}


@router.put("/{work_id}/gene")
def update_gene(work_id: str, req: GeneEditReq):
    work = db.get_work(work_id)
    if not work:
        raise HTTPException(404, "作品不存在")
    data = work.gene.model_dump()
    data.update(req.gene or {})
    work.gene = work.gene.model_validate(data)
    work.stage = max(work.stage, 2)
    db.save_work(work)
    return work.gene.model_dump()


@router.put("/{work_id}/characters")
def update_characters(work_id: str, req: CharacterEditReq):
    work = db.get_work(work_id)
    if not work:
        raise HTTPException(404, "作品不存在")
    chars = []
    for c in req.characters or []:
        if not c.get("id"):
            c["id"] = slugify(c.get("name", "role"))
        chars.append(Character.model_validate(c))
    work.characters = chars
    work.stage = max(work.stage, 3)
    db.save_work(work)
    return [c.model_dump() for c in work.characters]


@router.put("/{work_id}/outline")
def update_outline(work_id: str, req: OutlineEditReq):
    work = db.get_work(work_id)
    if not work:
        raise HTTPException(404, "作品不存在")
    if req.beats is not None:
        work.outline.beats = [Beat.model_validate(b) for b in req.beats]
    if req.threads is not None:
        work.outline.threads = [Thread.model_validate(t) for t in req.threads]
    if req.locked is not None:
        work.outline.locked = req.locked
        if req.locked:
            _split_into_chapters(work)
            work.stage = max(work.stage, 4)
    db.save_work(work)
    return work.outline.model_dump()


@router.get("/{work_id}/chapters")
def get_chapters(work_id: str):
    work = db.get_work(work_id)
    if not work:
        raise HTTPException(404, "作品不存在")
    return [c.model_dump() for c in work.chapters]


@router.put("/{work_id}/chapters/{num}/brief")
def update_chapter_brief(work_id: str, num: int, req: ChapterBriefReq):
    work = db.get_work(work_id)
    if not work:
        raise HTTPException(404, "作品不存在")
    for ch in work.chapters:
        if ch.num == num:
            ch.brief = req.brief
            db.save_work(work)
            return ch.model_dump()
    raise HTTPException(404, "章节不存在")


def _split_into_chapters(work) -> None:
    """大纲锁定后，按主线节点拆分章节卡片。"""
    if work.chapters:
        return
    chapters = []
    for i, beat in enumerate(sorted(work.outline.beats, key=lambda b: b.order), start=1):
        chapters.append(Chapter(
            num=i,
            title=beat.title or f"第{i}章",
            status="todo",
            cast=beat.cast,
            brief=beat.summary,
        ))
    work.chapters = chapters
