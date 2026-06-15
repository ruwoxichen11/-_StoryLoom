"""故事织机 - 设定服务

负责：
- 把作品的故事基因 / 角色 / 大纲拼成"世界设定文本"（喂给各 Agent 的 work_setting）
- 把这些设定切块灌入 RAG 向量库（供 ReAct 演绎体检索）
"""
from __future__ import annotations

from app.core import bootstrap  # noqa: F401  确保顶层包可导入
from rag import LoreStore
from utils import settings as _settings
from utils.textkit import split_text
from app.models import Work


def build_work_setting(work: Work) -> str:
    """汇总作品级设定文本。"""
    g = work.gene
    lines = [
        f"作品：{work.title}",
        f"题材：{g.genre}　基调：{g.mood}",
        f"核心矛盾：{g.core_tension}",
        f"世界观前提：{g.world_premise}",
    ]
    if g.keywords:
        lines.append("关键词：" + "、".join(g.keywords))
    if work.characters:
        lines.append("登场角色：")
        for c in work.characters:
            lines.append(
                f"  - {c.name}（{c.archetype}）：{c.temper}；动机={c.drive}；弱点={c.flaw}"
            )
    return "\n".join(lines)


def reindex_lore(work: Work) -> dict:
    """把作品设定重新灌入向量库，返回入库统计。"""
    store = LoreStore(work.id)
    cs = _settings.get("rag.chunk_size", 480)
    ov = _settings.get("rag.chunk_overlap", 80)

    docs: list[tuple[str, str]] = []  # (category, text)

    g = work.gene
    if g.world_premise:
        docs.append(("world", f"世界观前提：{g.world_premise}"))
    if g.core_tension:
        docs.append(("world", f"核心矛盾：{g.core_tension}"))
    for c in work.characters:
        docs.append((
            "character",
            f"角色{c.name}（{c.archetype}）：外形{c.look}；性格{c.temper}；"
            f"动机{c.drive}；弱点{c.flaw}；口头禅{c.tagline}",
        ))
    for b in work.outline.beats:
        docs.append(("plot", f"第{b.order}节《{b.title}》：{b.summary}"))
    # 已成稿章节也入库，供后续章节回看前情
    for ch in work.chapters:
        if ch.manuscript:
            for chunk in split_text(ch.manuscript, cs, ov):
                docs.append(("recap", f"第{ch.num}章前情：{chunk}"))

    by_cat: dict[str, list[str]] = {}
    for cat, text in docs:
        by_cat.setdefault(cat, []).append(text)

    total = 0
    for cat, texts in by_cat.items():
        total += store.add(texts, category=cat)

    return {"indexed": total, "backend": store.backend, "total_in_store": store.count()}
