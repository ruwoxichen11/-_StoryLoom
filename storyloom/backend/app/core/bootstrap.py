"""故事织机 - 启动引导

把项目根目录（storyloom/）注入 sys.path，
使后端能直接 import 顶层的 agent / model / rag / utils 包。
任何 backend 模块在导入这些顶层包之前，应先 import 本模块。
"""
import sys
from pathlib import Path

# core/bootstrap.py -> core -> app -> backend -> storyloom/
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
