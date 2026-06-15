"""故事织机 - 文本向量化

策略：
1. 若配置了 embedding API（OpenAI 兼容协议），优先调用真实 embedding。
2. 任何失败 / 未配置时，回落到「本地哈希向量」——零依赖、可复现，
   足以让整条 RAG 流水线在没有外网或没填 key 时也能跑通。

返回向量维度固定为 config.embedding.dim（默认 256）。
"""
from __future__ import annotations

import hashlib
import math
from typing import List

import httpx

from utils import settings


def _dim() -> int:
    return int(settings.get("embedding.dim", 256) or 256)


def _hash_embed(text: str, dim: int) -> List[float]:
    """确定性哈希向量：把词散列到各维并做 L2 归一化。"""
    vec = [0.0] * dim
    text = text or ""
    tokens = text.lower().split() or [text]
    for tok in tokens:
        h = hashlib.md5(tok.encode("utf-8")).digest()
        for i in range(0, len(h), 2):
            idx = (h[i] << 8 | h[i + 1]) % dim
            sign = 1.0 if (h[i] & 1) else -1.0
            vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _api_embed(texts: List[str], dim: int) -> List[List[float]]:
    """调用 OpenAI 兼容 embedding 接口；维度不符时截断/补零。"""
    api_key = settings.get("embedding.api_key", "") or settings.deepseek_key()
    base_url = settings.get("embedding.base_url", "https://api.deepseek.com/v1")
    model = settings.get("embedding.model", "")
    if not api_key or not model:
        raise RuntimeError("embedding api not configured")

    resp = httpx.post(
        f"{base_url}/embeddings",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "input": texts},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    out: List[List[float]] = []
    for item in data:
        v = item["embedding"]
        if len(v) >= dim:
            v = v[:dim]
        else:
            v = v + [0.0] * (dim - len(v))
        out.append(v)
    return out


def embed_texts(texts: List[str]) -> List[List[float]]:
    """批量向量化，自动在 API 与本地哈希之间择优回落。"""
    dim = _dim()
    if not texts:
        return []
    use_fallback = bool(settings.get("embedding.use_local_hash_fallback", True))
    try:
        if settings.get("embedding.model"):
            return _api_embed(texts, dim)
        raise RuntimeError("no embedding model set")
    except Exception:
        if use_fallback:
            return [_hash_embed(t, dim) for t in texts]
        raise


def embed_query(text: str) -> List[float]:
    return embed_texts([text])[0]
