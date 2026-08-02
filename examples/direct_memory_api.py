"""直接使用 Mem0 API 的示例，不经过 Agent。

适合批量导入记忆、离线分析、外部系统同步等场景。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.long_term import LongTermMemory  # noqa: E402


def main() -> None:
    ltm = LongTermMemory()
    user_id = "alice"

    # 批量写入
    ltm.add(
        messages=[
            {"role": "user", "content": "我叫 Alice"},
            {"role": "assistant", "content": "好的，Alice。"},
            {"role": "user", "content": "我是前端工程师，主要用 TypeScript"},
        ],
        user_id=user_id,
        metadata={"source": "onboarding"},
    )

    # 语义检索
    hits = ltm.search(query="她做什么工作?", user_id=user_id, limit=5)
    print("检索结果:")
    for h in hits:
        print(f"  - {h.get('memory')} (score={h.get('score')})")

    # 列出全部
    print("\n全部记忆:")
    for m in ltm.get_all(user_id=user_id, limit=100):
        print(f"  - [{m.get('id')}] {m.get('memory')}")


if __name__ == "__main__":
    main()
