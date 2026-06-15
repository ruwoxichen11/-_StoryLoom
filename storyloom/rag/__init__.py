"""故事织机 - RAG 检索层（设定档案库）

把作品的世界观/角色/前情设定切块、向量化后存入 Milvus Lite，
供 ReAct 智能体在创作时检索，保证长篇一致性。

对外：
- LoreStore(work_id)  某部作品的设定向量库
"""
from .store import LoreStore

__all__ = ["LoreStore"]
