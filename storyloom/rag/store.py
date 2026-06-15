"""故事织机 - 设定向量库（Milvus Lite）

每部作品独立一个 collection，存放设定/前情切块及其向量。
优先使用 Milvus Lite（pymilvus 的本地文件模式）；若 pymilvus 不可用，
自动回落到「内存 + 本地 JSON 持久化 + 余弦相似度」的轻量实现，
确保零依赖环境下整条 RAG 链路依旧可跑。
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import List, Dict, Any

from utils import settings
from utils.paths import VECTOR_DIR
from .embedder import embed_texts, embed_query, _dim

try:
    from pymilvus import MilvusClient  # type: ignore
    _HAS_MILVUS = True
except Exception:  # noqa: BLE001
    _HAS_MILVUS = False


def _safe_name(work_id: str) -> str:
    prefix = settings.get("rag.collection_prefix", "loom_")
    clean = re.sub(r"[^0-9a-zA-Z_]", "_", work_id)
    return f"{prefix}{clean}"[:200]


class LoreStore:
    """某部作品的设定档案向量库。"""

    def __init__(self, work_id: str) -> None:
        self.work_id = work_id
        self.collection = _safe_name(work_id)
        self.dim = _dim()
        self.top_k = int(settings.get("rag.top_k", 4))
        # 优先 Milvus Lite；若运行环境不支持（如 Windows 缺 milvus-lite），
        # 自动回落到本地余弦检索，保证流程不中断。
        if _HAS_MILVUS:
            try:
                self._init_milvus()
                self._backend = "milvus"
            except Exception:  # noqa: BLE001
                self._backend = "local"
                self._init_local()
        else:
            self._backend = "local"
            self._init_local()

    # ---------- Milvus Lite ----------
    def _init_milvus(self) -> None:
        db_path = str(VECTOR_DIR / settings.get("rag.db_path", "data/vector_store.db").split("/")[-1])
        self._client = MilvusClient(db_path)
        if not self._client.has_collection(self.collection):
            self._client.create_collection(
                collection_name=self.collection,
                dimension=self.dim,
                metric_type="COSINE",
                auto_id=True,
            )

    # ---------- 本地回落 ----------
    def _local_file(self) -> Path:
        return VECTOR_DIR / f"{self.collection}.jsonl"

    def _init_local(self) -> None:
        self._records: List[Dict[str, Any]] = []
        f = self._local_file()
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._records.append(json.loads(line))

    def _persist_local(self) -> None:
        f = self._local_file()
        with open(f, "w", encoding="utf-8") as fp:
            for r in self._records:
                fp.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---------- 公共接口 ----------
    def add(self, texts: List[str], category: str = "lore") -> int:
        """把若干文本切块向量化并入库，返回写入条数。"""
        texts = [t.strip() for t in texts if t and t.strip()]
        if not texts:
            return 0
        vectors = embed_texts(texts)
        if self._backend == "milvus":
            rows = [
                {"vector": vectors[i], "text": texts[i], "category": category}
                for i in range(len(texts))
            ]
            self._client.insert(collection_name=self.collection, data=rows)
        else:
            for i, t in enumerate(texts):
                self._records.append(
                    {"vector": vectors[i], "text": t, "category": category}
                )
            self._persist_local()
        return len(texts)

    def search(self, query: str, top_k: int | None = None) -> List[Dict[str, Any]]:
        """检索最相关的设定片段。返回 [{text, category, score}]。"""
        k = top_k or self.top_k
        if self._backend == "milvus":
            qv = embed_query(query)
            res = self._client.search(
                collection_name=self.collection,
                data=[qv],
                limit=k,
                output_fields=["text", "category"],
            )
            hits = res[0] if res else []
            return [
                {
                    "text": h["entity"].get("text", ""),
                    "category": h["entity"].get("category", ""),
                    "score": round(float(h.get("distance", 0)), 4),
                }
                for h in hits
            ]
        # 本地余弦检索
        if not self._records:
            return []
        qv = embed_query(query)
        scored = []
        for r in self._records:
            scored.append((self._cosine(qv, r["vector"]), r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"text": r["text"], "category": r["category"], "score": round(s, 4)}
            for s, r in scored[:k]
        ]

    def count(self) -> int:
        if self._backend == "milvus":
            try:
                stats = self._client.get_collection_stats(self.collection)
                return int(stats.get("row_count", 0))
            except Exception:  # noqa: BLE001
                return 0
        return len(self._records)

    @property
    def backend(self) -> str:
        return self._backend

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(y * y for y in b)) or 1.0
        return dot / (na * nb)
