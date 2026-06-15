"""故事织机 - 通用工具包"""
from .paths import ROOT_DIR, CONFIG_FILE, DATA_DIR, FRONTEND_DIR
from .settings import settings
from .textkit import count_cn_words, extract_json, split_text, slugify

__all__ = [
    "ROOT_DIR", "CONFIG_FILE", "DATA_DIR", "FRONTEND_DIR",
    "settings", "count_cn_words", "extract_json", "split_text", "slugify",
]
