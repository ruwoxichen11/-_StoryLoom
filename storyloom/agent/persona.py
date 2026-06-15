"""故事织机 - 人格层叠组装器

把多层约束拼成一个完整的 system prompt：
    [织机总则] -> [作品设定] -> [本章约束] -> [角色专属]
越靠后的层级优先级越高（更贴近当前任务）。
"""
from __future__ import annotations

from typing import Dict, Optional

from utils import settings


_SECTION_TITLES = {
    "global": "【织机总则】",
    "work": "【作品设定】",
    "chapter": "【本章约束】",
    "role": "【角色专属指令】",
}


def compose_system_prompt(
    role_instruction: str = "",
    work_setting: str = "",
    chapter_setting: str = "",
    variables: Optional[Dict[str, str]] = None,
) -> str:
    """组装分层 system prompt。"""
    layers = [
        ("global", settings.get("global_persona", "")),
        ("work", work_setting),
        ("chapter", chapter_setting),
        ("role", role_instruction),
    ]
    blocks = []
    for key, content in layers:
        content = (content or "").strip()
        if content:
            blocks.append(f"{_SECTION_TITLES[key]}\n{content}")
    prompt = "\n\n".join(blocks)

    if variables:
        for k, v in variables.items():
            prompt = prompt.replace(f"{{{{{k}}}}}", str(v))
    return prompt
