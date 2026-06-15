#!/usr/bin/env python3
"""故事织机 StoryLoom · 一键启动

    python run.py

自动安装依赖并拉起 FastAPI 服务，浏览器访问首页即可使用。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
REQ = BACKEND / "requirements.txt"
CONFIG = ROOT / "config" / "settings.json"

BANNER = r"""
   ____  _                  _
  / ___|| |_ ___  _ __ _   _| |    ___   ___  _ __ ___
  \___ \| __/ _ \| '__| | | | |   / _ \ / _ \| '_ ` _ \
   ___) | || (_) | |  | |_| | |__| (_) | (_) | | | | | |
  |____/ \__\___/|_|   \__, |_____\___/ \___/|_| |_| |_|
        故事织机        |___/   LangChain · 多智能体小说工作台
"""


def ensure_deps():
    print("[织机] 检查 Python 依赖（首次启动可能耗时较久）…")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(REQ), "-q"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print("[织机] 依赖就绪")
    except subprocess.CalledProcessError:
        print("[织机] 自动安装失败，请手动执行： pip install -r", REQ)


def read_port() -> int:
    if CONFIG.exists():
        try:
            return json.loads(CONFIG.read_text(encoding="utf-8")).get("server", {}).get("port", 8200)
        except Exception:
            pass
    return 8200


def main():
    print(BANNER)
    ensure_deps()
    port = read_port()
    print(f"\n[织机] 启动服务 …")
    print(f"[织机] 打开首页： http://localhost:{port}")
    print(f"[织机] 接口文档： http://localhost:{port}/docs")
    print(f"[织机] Ctrl+C 退出\n")

    # 把项目根加入 PYTHONPATH，让 backend 能 import 顶层 agent/model/rag/utils
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    os.chdir(str(BACKEND))
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", str(port), "--reload"],
        env=env,
    )


if __name__ == "__main__":
    main()
