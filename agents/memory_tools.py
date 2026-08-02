"""把 Mem0 长期记忆封装为 Strands 工具，供 Agent 主动调用。

设计思路：
- Agent 在对话中判断"值得记住"的信息时，主动调用 remember 写入长期记忆
- 需要唤起过往信息时，调用 recall 做语义检索
- 通过闭包传入 user_id / agent_id，工具签名保持简洁
"""
from __future__ import annotations

from typing import List, Optional

from strands import tool

from memory.long_term import LongTermMemory


def build_memory_tools(
    long_term: LongTermMemory,
    user_id: str,
    agent_id: Optional[str] = None,
) -> List:
    """构造绑定到具体 user 的记忆工具集。返回 [remember, recall, forget]。"""

    @tool
    def remember(content: str) -> str:
        """把一条关于当前用户的重要信息保存到长期记忆。

        Mem0 会用 LLM 从内容中抽取值得留存的事实（偏好、身份、约定等），
        并做去重与冲突消解。适用于：用户明确告知的偏好、事实性信息、
        长期有效的约定。

        Args:
            content: 需要记住的原始文本。可以是一句话，也可以是一段对话摘要。

        Returns:
            记忆写入结果的简要描述。
        """
        result = long_term.add(
            messages=content,
            user_id=user_id,
            agent_id=agent_id,
        )
        # Mem0 v2.x 只返回 ADD 事件 (累积式记忆,通过 linked_memory_ids 关联旧记忆)
        # 返回结构: {"results": [{"id": ..., "memory": ..., "event": "ADD"}, ...]}
        events = result.get("results", []) if isinstance(result, dict) else []
        if not events:
            return "已提交长期记忆（未抽取到值得留存的新事实）。"
        summary = "; ".join(e.get("memory", "") for e in events if e.get("memory"))
        return f"已写入 {len(events)} 条长期记忆：{summary}"

    @tool
    def recall(query: str, limit: int = 5) -> str:
        """按语义检索当前用户的长期记忆。

        用于回答关于用户偏好、历史事实的问题，或在对话前主动唤起相关上下文。

        Args:
            query: 检索用的自然语言问题或关键词。
            limit: 返回条数上限，默认 5。

        Returns:
            按相关度排序的记忆条目文本；无命中时返回提示语。
        """
        # threshold=0.0: 关闭 Mem0 内部机器过滤,把 top-N 都返回让 LLM 自行判断。
        # Mem0 v2 默认 threshold=0.1 在跨语言 / 融合评分下常常把有效记忆过滤掉。
        hits = long_term.search(
            query=query,
            user_id=user_id,
            agent_id=agent_id,
            limit=limit,
            threshold=0.0,
        )
        if not hits:
            return "未在长期记忆中找到相关内容。"
        lines = []
        for i, h in enumerate(hits, 1):
            text = h.get("memory") or h.get("text") or ""
            score = h.get("score")
            score_str = f" (score={score:.3f})" if isinstance(score, (int, float)) else ""
            lines.append(f"{i}. {text}{score_str}")
        return "\n".join(lines)

    @tool
    def forget(memory_id: str) -> str:
        """删除一条特定的长期记忆。

        Args:
            memory_id: 记忆条目的 ID。可通过 recall 返回结果中的 id 获取。

        Returns:
            删除结果描述。
        """
        long_term.delete(memory_id=memory_id)
        return f"已删除记忆 {memory_id}"

    return [remember, recall, forget]
