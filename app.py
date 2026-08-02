"""CLI 入口 —— 交互式对话，方便快速体验。

用法:
    python app.py [--session SESSION_ID] [--user USER_ID]

在会话中输入 :quit 退出，:clear 清空当前 session 的短期记忆。
"""
from __future__ import annotations

import argparse
import sys
import uuid

from agents import build_memory_agent
from memory.session import build_session_manager


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--session", default=f"cli-{uuid.uuid4().hex[:8]}")
    p.add_argument("--user", default="cli-user")
    p.add_argument("--agent-id", default="default")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    print(f"[session={args.session}] [user={args.user}] 输入 :quit 退出\n")

    agent = build_memory_agent(
        session_id=args.session,
        user_id=args.user,
        agent_id=args.agent_id,
    )

    while True:
        try:
            line = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not line:
            continue
        if line in (":quit", ":q", ":exit"):
            return 0
        if line == ":clear":
            sm = build_session_manager(args.session)
            sm.delete_session(args.session)
            print("(短期记忆已清空)")
            # 重建 agent, 让 session_manager 重新初始化
            agent = build_memory_agent(
                session_id=args.session,
                user_id=args.user,
                agent_id=args.agent_id,
            )
            continue

        try:
            response = agent(line)
        except Exception as e:  # noqa: BLE001
            print(f"[error] {e}")
            continue

        print(response)
        print()


if __name__ == "__main__":
    sys.exit(main())
