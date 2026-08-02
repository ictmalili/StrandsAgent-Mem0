"""长期记忆 —— 使用 Mem0 + OpenSearch。

Mem0 会在 add() 时调用 LLM 从原始对话抽取"值得记住"的事实（用户偏好、身份、
决策等），并向量化存入 OpenSearch。search() 做语义检索，命中的记忆将作为
提示上下文注入 Agent。
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Union

# ------ 抑制 Mem0 的可选/无害日志 ------
# 1) 关闭遥测: 消除 [PostHog] Multiple active PostHog clients 警告
os.environ.setdefault("MEM0_TELEMETRY", "false")
# 2) 抑制 spaCy 未装的 error 日志 (可选实体链接功能, 不影响主流程)
logging.getLogger("mem0").setLevel(logging.WARNING)
logging.getLogger("mem0.memory.entity_extractor").setLevel(logging.CRITICAL)

from mem0 import Memory  # noqa: E402

from config.mem0_config import build_mem0_config  # noqa: E402


class LongTermMemory:
    """对 Mem0 SDK 的薄封装，绑定项目内的默认配置。"""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or build_mem0_config()
        self._memory = Memory.from_config(self._config)

    # ------------------------------------------------------------------ #
    # 写入
    # ------------------------------------------------------------------ #
    def add(
        self,
        messages: Union[str, List[Dict[str, str]]],
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """把一段对话或文本加入长期记忆。

        Args:
            messages: 完整消息列表（推荐）或纯文本。
            user_id: 用户 ID，跨 session 持久保留。
            agent_id: agent 维度（区分不同角色/机器人）。
            run_id: 单次会话/任务 ID（可选）。
            metadata: 附加信息。
        """
        return self._memory.add(
            messages=messages,
            user_id=user_id,
            agent_id=agent_id,
            run_id=run_id,
            metadata=metadata or {},
        )

    # ------------------------------------------------------------------ #
    # 检索
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_filters(
        user_id: Optional[str],
        agent_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Mem0 v2 要求 user_id / agent_id 通过 filters dict 传入。"""
        f: Dict[str, Any] = {}
        if user_id:
            f["user_id"] = user_id
        if agent_id:
            f["agent_id"] = agent_id
        return f or None

    def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 5,
        threshold: Optional[float] = None,
        rerank: bool = False,
    ) -> List[Dict[str, Any]]:
        """按 query 做语义检索，返回命中的记忆列表。

        Mem0 v2 API:
        - user_id / agent_id 通过 ``filters`` dict 传入
        - 融合评分 (语义 + BM25 + 实体):
          - ``threshold``: 结果最低相关度 (默认 0.1, 传 0.0 关闭过滤)
          - ``rerank``: 是否启用 LLM/Cross-Encoder 重排
        """
        kwargs: Dict[str, Any] = {
            "query": query,
            "limit": limit,
            "rerank": rerank,
        }
        filters = self._build_filters(user_id, agent_id)
        if filters:
            kwargs["filters"] = filters
        if threshold is not None:
            kwargs["threshold"] = threshold
        result = self._memory.search(**kwargs)
        if isinstance(result, dict):
            return result.get("results", [])
        return result or []

    def get_all(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        kwargs: Dict[str, Any] = {"limit": limit}
        filters = self._build_filters(user_id, agent_id)
        if filters:
            kwargs["filters"] = filters
        result = self._memory.get_all(**kwargs)
        if isinstance(result, dict):
            return result.get("results", [])
        return result or []

    # ------------------------------------------------------------------ #
    # 更新 / 删除
    # ------------------------------------------------------------------ #
    def update(self, memory_id: str, data: str) -> Dict[str, Any]:
        return self._memory.update(memory_id=memory_id, data=data)

    def delete(self, memory_id: str) -> Dict[str, Any]:
        return self._memory.delete(memory_id=memory_id)

    def delete_all(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._memory.delete_all(user_id=user_id, agent_id=agent_id)

    def history(self, memory_id: str) -> List[Dict[str, Any]]:
        return self._memory.history(memory_id=memory_id)
