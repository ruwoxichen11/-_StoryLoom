"""故事织机 - LLM 模型层

统一通过 LangChain 的 ChatOpenAI 接入 DeepSeek（OpenAI 兼容协议）。
对外暴露：
- get_chat(role)        按角色取一个 LangChain ChatModel
- astream_chat(...)     便捷的异步流式生成
"""
from .llm_factory import get_chat, astream_chat, has_api_key

__all__ = ["get_chat", "astream_chat", "has_api_key"]
