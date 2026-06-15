"""故事织机 - ReAct 工具箱（Tool Routing）

为角色演绎体提供可调用的工具，让它在发言前能：
- lore_lookup    检索设定档案库（RAG / Milvus）
- recall_scene   回看本场近期对话，避免重复或矛盾
- continuity_note 记下一条需要保持一致的线索

工具用 LangChain 的 StructuredTool 封装，可直接挂进 ReAct AgentExecutor。
"""
from __future__ import annotations

from typing import List, Callable

from langchain_core.tools import StructuredTool

from rag import LoreStore


def build_actor_tools(
    work_id: str,
    recent_scene_getter: Callable[[], str],
) -> List[StructuredTool]:
    """为某次演绎构建一组工具。

    recent_scene_getter: 返回当前场景最近若干条对话文本的回调。
    """
    store = LoreStore(work_id)

    def lore_lookup(query: str) -> str:
        """根据关键词检索世界观、角色背景、前情设定等档案，返回最相关的片段。"""
        hits = store.search(query)
        if not hits:
            return "（设定库暂无相关条目，可凭已知信息合理推断）"
        lines = [f"[{h['category']}|{h['score']}] {h['text']}" for h in hits]
        return "检索到的设定片段：\n" + "\n".join(lines)

    def recall_scene(_: str = "") -> str:
        """回看当前场景最近发生的对话与动作，用于保持上下文连贯。"""
        text = recent_scene_getter() or ""
        return text or "（当前场景尚无对话）"

    return [
        StructuredTool.from_function(
            func=lore_lookup,
            name="lore_lookup",
            description="检索作品设定库（世界观/角色/前情）。当你不确定某个设定、人名、地点、历史时调用，输入要查询的关键词。",
        ),
        StructuredTool.from_function(
            func=recall_scene,
            name="recall_scene",
            description="回看本场最近的对话与动作，确认上下文。无需参数。",
        ),
    ]
