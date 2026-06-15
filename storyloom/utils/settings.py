"""故事织机 - 配置读写

封装 config/settings.json 的加载、点分路径取值、热更新与持久化。
支持环境变量覆盖 DeepSeek API Key（DEEPSEEK_API_KEY）。
"""
import json
import os
import threading
from typing import Any

from .paths import CONFIG_FILE


class Settings:
    """全局配置单例（线程安全的读写）"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            else:
                self._data = {}

    def _persist(self) -> None:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """用 'a.b.c' 形式取值"""
        with self._lock:
            node: Any = self._data
            for part in dotted_key.split("."):
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    return default
            return node

    def all(self) -> dict:
        with self._lock:
            return json.loads(json.dumps(self._data))  # 深拷贝

    def update(self, patch: dict) -> None:
        """深合并并落盘"""
        with self._lock:
            self._deep_merge(self._data, patch)
            self._persist()

    def deepseek_key(self) -> str:
        """优先取环境变量，其次取配置文件"""
        env = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if env:
            return env
        return self.get("providers.deepseek.api_key", "") or ""

    def deepseek_base_url(self) -> str:
        return self.get("providers.deepseek.base_url", "https://api.deepseek.com/v1")

    def model_for(self, role: str) -> str:
        """按角色名取对应模型，找不到回落到 actor 配置"""
        routes = self.get("role_models", {}) or {}
        return routes.get(role, routes.get("actor", "deepseek-chat"))

    @staticmethod
    def _deep_merge(base: dict, patch: dict) -> None:
        for k, v in patch.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                Settings._deep_merge(base[k], v)
            else:
                base[k] = v


# 全局单例
settings = Settings()
