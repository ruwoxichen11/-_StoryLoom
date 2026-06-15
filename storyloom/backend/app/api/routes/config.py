"""设置路由：读写配置、查可用模型、自检"""
from __future__ import annotations

from fastapi import APIRouter

from app.core import bootstrap  # noqa: F401
from app.schemas import SettingsPatchReq
from utils import settings
from model import has_api_key
from rag import LoreStore

router = APIRouter()

AVAILABLE_MODELS = [
    {"id": "deepseek-chat", "name": "DeepSeek-V3", "note": "经济快速，适合演绎/润色"},
    {"id": "deepseek-reasoner", "name": "DeepSeek-R1", "note": "强推理，适合规划/审稿"},
]


def _mask(cfg: dict) -> dict:
    """脱敏返回：隐藏 api_key 具体值，只显示是否已配置。"""
    import copy
    safe = copy.deepcopy(cfg)
    prov = safe.get("providers", {}).get("deepseek", {})
    if "api_key" in prov:
        prov["api_key"] = "********" if prov["api_key"] else ""
    emb = safe.get("embedding", {})
    if emb.get("api_key"):
        emb["api_key"] = "********"
    return safe


@router.get("")
def get_config():
    return {"config": _mask(settings.all()), "has_key": has_api_key()}


@router.put("")
def update_config(req: SettingsPatchReq):
    settings.update(req.patch or {})
    return {"config": _mask(settings.all()), "has_key": has_api_key()}


@router.get("/models")
def models():
    return {"models": AVAILABLE_MODELS, "role_models": settings.get("role_models", {})}


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "故事织机 StoryLoom",
        "has_key": has_api_key(),
    }


@router.get("/rag-status/{work_id}")
def rag_status(work_id: str):
    store = LoreStore(work_id)
    return {"backend": store.backend, "count": store.count()}
