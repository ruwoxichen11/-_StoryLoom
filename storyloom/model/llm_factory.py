"""故事织机 - LLM 工厂

用 LangChain 的 ChatOpenAI 封装 DeepSeek（V3=deepseek-chat, R1=deepseek-reasoner）。
按「角色名 -> 模型」路由（见 config/settings.json 的 role_models）。
"""
from __future__ import annotations

from typing import AsyncGenerator, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage

from utils import settings


def has_api_key() -> bool:
    return bool(settings.deepseek_key())


def get_chat(
    role: str = "actor",
    temperature: float = 0.8,
    max_tokens: int = 2048,
    streaming: bool = True,
) -> ChatOpenAI:
    """按角色返回一个配置好的 LangChain ChatModel。

    role 决定具体用哪个 DeepSeek 模型（强模型 reasoner / 经济模型 chat）。
    """
    model_name = settings.model_for(role)
    return ChatOpenAI(
        model=model_name,
        api_key=settings.deepseek_key() or "sk-placeholder",
        base_url=settings.deepseek_base_url(),
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming,
        timeout=120,
    )


def _to_lc_messages(
    system_prompt: str,
    user_message: str,
    history: Optional[List[dict]] = None,
) -> List[BaseMessage]:
    """把朴素的 dict 历史转成 LangChain Message 列表"""
    msgs: List[BaseMessage] = []
    if system_prompt:
        msgs.append(SystemMessage(content=system_prompt))
    for h in history or []:
        role = h.get("role")
        content = h.get("content", "")
        if role == "assistant":
            msgs.append(AIMessage(content=content))
        else:
            msgs.append(HumanMessage(content=content))
    msgs.append(HumanMessage(content=user_message))
    return msgs


async def astream_chat(
    role: str,
    system_prompt: str,
    user_message: str,
    history: Optional[List[dict]] = None,
    temperature: float = 0.8,
    max_tokens: int = 2048,
) -> AsyncGenerator[str, None]:
    """异步流式生成，逐 token yield 文本。"""
    if not has_api_key():
        yield "[未配置 DeepSeek API Key] 请在「设置」中填入密钥后重试。"
        return

    chat = get_chat(role, temperature=temperature, max_tokens=max_tokens, streaming=True)
    messages = _to_lc_messages(system_prompt, user_message, history)
    try:
        async for chunk in chat.astream(messages):
            text = chunk.content
            if text:
                yield text if isinstance(text, str) else str(text)
    except Exception as exc:  # noqa: BLE001
        yield f"[模型调用异常] {exc}"


async def acomplete(
    role: str,
    system_prompt: str,
    user_message: str,
    history: Optional[List[dict]] = None,
    temperature: float = 0.8,
    max_tokens: int = 2048,
) -> str:
    """异步一次性生成完整文本（内部仍走流式累积）。"""
    parts: list[str] = []
    async for piece in astream_chat(
        role, system_prompt, user_message, history, temperature, max_tokens
    ):
        parts.append(piece)
    return "".join(parts)
