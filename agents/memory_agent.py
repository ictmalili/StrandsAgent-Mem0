"""带记忆能力的 Strands Agent 构造器。

组合:
- 模型: OpenAI 兼容 (DeepSeek / Qwen / GLM / OpenAI 直连) 或 Amazon Bedrock (海外区)
- 短期记忆: SlidingWindowConversationManager + S3/File SessionManager
- 长期记忆: Mem0 (Aurora PG / OpenSearch), 通过 tool 暴露给模型
"""
from __future__ import annotations

from typing import List, Optional

from strands import Agent
from strands.models.openai import OpenAIModel

from config.settings import settings
from memory.long_term import LongTermMemory
from memory.session import build_conversation_manager, build_session_manager

from .memory_tools import build_memory_tools


_DEFAULT_SYSTEM_PROMPT = """你是一个具备长期记忆能力的智能助手。

关于记忆的使用规则:
1. 当用户提供**长期有效**的信息时 (偏好、身份、约定、事实), 主动调用 remember 工具保存。
2. 当用户提问涉及**历史信息**或需要个性化回答时, 先调用 recall 工具检索长期记忆。
3. 不要把闲聊内容或临时问答塞进长期记忆。
4. 用中文自然回答, 不要显式提及"工具"或"记忆库"等实现细节。
"""

_OPENAI_STYLE_PROVIDERS = {
    "deepseek", "qwen", "zhipu", "openai_compatible", "openai"
}


def build_model():
    """按 settings.llm_provider 构造 Strands 模型。

    - OpenAI 兼容系: OpenAIModel + base_url
    - Bedrock: BedrockModel (只在海外区可用)
    """
    provider = settings.llm_provider

    if provider in _OPENAI_STYLE_PROVIDERS:
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY 未配置")
        return OpenAIModel(
            client_args={
                "api_key": settings.llm_api_key,
                "base_url": settings.llm_base_url,
            },
            model_id=settings.llm_model,
            params={
                "temperature": settings.llm_temperature,
                "max_tokens": settings.llm_max_tokens,
            },
        )

    if provider == "bedrock":
        # 仅在有海外区 Bedrock 访问时可用
        from strands.models import BedrockModel
        return BedrockModel(
            model_id=settings.llm_model,
            region_name=settings.bedrock_region,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

    raise ValueError(f"未知的 LLM_PROVIDER: {provider}")


def build_memory_agent(
    session_id: str,
    user_id: str,
    agent_id: str = "default",
    system_prompt: Optional[str] = None,
    extra_tools: Optional[List] = None,
    long_term: Optional[LongTermMemory] = None,
) -> Agent:
    """创建一个带完整记忆能力的 Agent。"""
    model = build_model()

    ltm = long_term or LongTermMemory()
    memory_tools = build_memory_tools(
        long_term=ltm, user_id=user_id, agent_id=agent_id
    )
    tools = list(memory_tools) + list(extra_tools or [])

    conversation_manager = build_conversation_manager()
    session_manager = build_session_manager(session_id=session_id)

    return Agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt or _DEFAULT_SYSTEM_PROMPT,
        agent_id=agent_id,
        conversation_manager=conversation_manager,
        session_manager=session_manager,
    )
