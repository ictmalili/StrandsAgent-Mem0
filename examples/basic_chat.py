"""最简示例：一个用户，一次会话，展示短期 + 长期记忆的工作方式。

运行前请配置好 .env（LLM_API_KEY / EMBEDDER_API_KEY / OPENSEARCH_HOST 等）。
"""
from __future__ import annotations

from agents import build_memory_agent


def main() -> None:
    session_id = "demo-session-001"
    user_id = "alice"

    agent = build_memory_agent(session_id=session_id, user_id=user_id)

    # 第 1 轮：告诉 Agent 一些长期有效的信息，期望它主动 remember
    print(">>> 用户: 我叫 Alice，是一名前端工程师，喜欢用 TypeScript。")
    print(agent("我叫 Alice，是一名前端工程师，喜欢用 TypeScript。"))

    # 第 2 轮：短期记忆生效 (同一 session)
    print("\n>>> 用户: 顺便再告诉你，我不喜欢吃香菜。")
    print(agent("顺便再告诉你，我不喜欢吃香菜。"))

    # 第 3 轮：新建 session,验证长期记忆生效
    print("\n--- 新建 session,验证长期记忆是否被唤起 ---")
    agent2 = build_memory_agent(session_id="demo-session-002", user_id=user_id)
    print(">>> 用户: 帮我推荐几家适合聚餐的餐厅。")
    print(agent2("帮我推荐几家适合聚餐的餐厅。"))


if __name__ == "__main__":
    main()
