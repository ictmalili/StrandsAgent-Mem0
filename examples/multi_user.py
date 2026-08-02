"""多用户示例：验证长期记忆按 user_id 隔离。"""
from __future__ import annotations

from agents import build_memory_agent
from memory.long_term import LongTermMemory


def main() -> None:
    ltm = LongTermMemory()  # 复用同一个 Mem0 实例即可

    # 用户 A
    alice = build_memory_agent(
        session_id="s-alice", user_id="alice", long_term=ltm
    )
    print(">>> Alice:", alice("请记住，我住在北京海淀。"))

    # 用户 B
    bob = build_memory_agent(
        session_id="s-bob", user_id="bob", long_term=ltm
    )
    print("\n>>> Bob:", bob("请记住，我住在上海浦东。"))

    # 分别检索
    print("\n>>> Alice: 我住哪儿?")
    print(alice("我住哪儿?"))

    print("\n>>> Bob: 我住哪儿?")
    print(bob("我住哪儿?"))


if __name__ == "__main__":
    main()
