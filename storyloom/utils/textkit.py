"""故事织机 - 文本处理小工具

包含：中文字数统计、从模型输出里抽取 JSON、长文切块、文件名安全化。
"""
import json
import re
import uuid
from typing import Optional


def count_cn_words(text: str) -> int:
    """估算中文字数：中文字符按 1 计，连续英文/数字按词计。"""
    if not text:
        return 0
    cn = len(re.findall(r"[\u4e00-\u9fff]", text))
    en_words = len(re.findall(r"[A-Za-z0-9]+", text))
    return cn + en_words


def extract_json(raw: str) -> Optional[dict]:
    """从可能夹带说明文字 / ```json 围栏的模型输出里，鲁棒地抽出第一个 JSON 对象。"""
    if not raw:
        return None
    # 去掉 markdown 代码围栏
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            pass
    # 退而求其次：取首个 { 到末个 } 的子串
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        candidate = raw[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            # 尝试逐步收缩右括号
            for e in range(end, start, -1):
                if raw[e] == "}":
                    try:
                        return json.loads(raw[start:e + 1])
                    except Exception:
                        continue
    return None


def split_text(text: str, chunk_size: int = 480, overlap: int = 80) -> list[str]:
    """按字符长度切块，块间保留 overlap 重叠，尽量在句号处断开。"""
    text = (text or "").strip()
    if not text:
        return []
    chunks: list[str] = []
    step = max(chunk_size - overlap, 1)
    i = 0
    n = len(text)
    while i < n:
        end = min(i + chunk_size, n)
        # 尝试在窗口内的最后一个句末标点处断开
        window = text[i:end]
        if end < n:
            m = list(re.finditer(r"[。！？；\n]", window))
            if m and m[-1].end() > chunk_size * 0.5:
                end = i + m[-1].end()
                window = text[i:end]
        chunks.append(window.strip())
        i += step if end >= i + step else (end - i)
    return [c for c in chunks if c]


def slugify(name: str) -> str:
    """生成短 id（保留可读性，附 6 位随机）"""
    base = re.sub(r"[^\w\u4e00-\u9fff]+", "-", (name or "work").strip())[:24].strip("-")
    return f"{base or 'work'}-{uuid.uuid4().hex[:6]}"
