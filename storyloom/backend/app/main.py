"""故事织机 StoryLoom - FastAPI 应用入口"""
from __future__ import annotations

from app.core import bootstrap  # noqa: F401  必须最先导入，注入 sys.path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from utils.paths import FRONTEND_DIR
from app.api.routes import works, config as config_route, generate, roundtable

app = FastAPI(title="StoryLoom API", description="故事织机 - 基于 LangChain 多智能体的小说创作工作台", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由
app.include_router(config_route.router, prefix="/api/settings", tags=["设置"])
app.include_router(works.router, prefix="/api/works", tags=["作品"])
app.include_router(generate.router, prefix="/api/gen", tags=["AI生成"])
app.include_router(roundtable.router, tags=["圆桌戏台"])


@app.get("/api/ping")
def ping():
    return {"ok": True, "service": "StoryLoom"}


# ---- 静态前端 ----
def _serve(filename: str, media: str | None = None):
    resp = FileResponse(str(FRONTEND_DIR / filename), media_type=media)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@app.get("/")
def index():
    return _serve("index.html")


@app.get("/app.js")
def appjs():
    return _serve("app.js", "application/javascript")


@app.get("/theme.css")
def themecss():
    return _serve("theme.css", "text/css")
