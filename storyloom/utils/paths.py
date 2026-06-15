"""故事织机 - 统一路径常量

所有模块通过这里拿到项目根目录及关键子目录，避免到处写相对路径。
"""
from pathlib import Path

# utils/paths.py -> utils/ -> 项目根 storyloom/
ROOT_DIR = Path(__file__).resolve().parent.parent

CONFIG_DIR = ROOT_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "settings.json"

DATA_DIR = ROOT_DIR / "data"
PROJECTS_DIR = DATA_DIR / "works"          # 每部作品一个子目录
VECTOR_DIR = DATA_DIR                       # Milvus Lite 数据库落盘目录

FRONTEND_DIR = ROOT_DIR / "frontend"

# 确保关键目录存在
for _d in (DATA_DIR, PROJECTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
