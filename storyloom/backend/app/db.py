"""故事织机 - JSON 文件存储

每部作品一个文件：data/works/{work_id}.json
提供作品的增删改查；并维护一个轻量索引（标题/阶段/更新时间）。
无数据库依赖。
"""
from __future__ import annotations

import json
import threading
from typing import List, Optional

from utils.paths import PROJECTS_DIR
from utils.textkit import slugify
from .models import Work


_LOCK = threading.RLock()


def _path(work_id: str):
    return PROJECTS_DIR / f"{work_id}.json"


def create_work(title: str, synopsis: str = "") -> Work:
    with _LOCK:
        work = Work(id=slugify(title or "work"), title=title or "未命名作品", synopsis=synopsis)
        _write(work)
        return work


def get_work(work_id: str) -> Optional[Work]:
    p = _path(work_id)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return Work.model_validate(json.load(f))


def list_works() -> List[dict]:
    out = []
    for p in sorted(PROJECTS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
            out.append({
                "id": d.get("id"),
                "title": d.get("title"),
                "stage": d.get("stage", 1),
                "updated_at": d.get("updated_at"),
                "chapters": len(d.get("chapters", [])),
            })
        except Exception:  # noqa: BLE001
            continue
    return out


def save_work(work: Work) -> Work:
    with _LOCK:
        from .models import _now
        work.updated_at = _now()
        _write(work)
        return work


def delete_work(work_id: str) -> bool:
    with _LOCK:
        p = _path(work_id)
        if p.exists():
            p.unlink()
            return True
        return False


def _write(work: Work) -> None:
    p = _path(work.id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(work.model_dump_json(indent=2))
