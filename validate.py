"""端到端连通性校验脚本。

依次检查:
  1. .env 加载
  2. LLM 调用 (走 Strands OpenAIModel / BedrockModel)
  3. Embedder 调用 (Mem0 embedder)
  4. S3 访问 (Session bucket 读写)
  5. Aurora PG + pgvector (Mem0 vector store)
  6. Mem0 端到端: add + search
  7. Strands Agent 完整对话闭环 (含 remember/recall 工具)

用法:
    python validate.py

有任何一步失败会立即抛错并打印详细信息, 方便定位。
"""
from __future__ import annotations

import sys
import traceback
import uuid
from datetime import datetime
from typing import Callable

import boto3

from config.settings import settings


# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
GRAY = "\033[90m"
RESET = "\033[0m"


def _step(name: str, fn: Callable[[], str]) -> bool:
    print(f"{YELLOW}[.] {name}...{RESET}")
    try:
        detail = fn() or ""
        print(f"{GREEN}[✓] {name}{RESET} {GRAY}{detail}{RESET}\n")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"{RED}[✗] {name}{RESET}")
        print(f"{RED}    {type(e).__name__}: {e}{RESET}")
        traceback.print_exc()
        print()
        return False


# --------------------------------------------------------------------------- #
# 单项检查
# --------------------------------------------------------------------------- #
def check_config() -> str:
    missing = []
    if settings.llm_provider in {"deepseek", "qwen", "zhipu", "openai_compatible", "openai"}:
        if not settings.llm_api_key:
            missing.append("LLM_API_KEY")
    if settings.embedder_provider in {"qwen", "zhipu", "openai_compatible", "openai"}:
        if not settings.embedder_api_key:
            missing.append("EMBEDDER_API_KEY")
    if settings.session_backend == "s3" and not settings.session_s3_bucket:
        missing.append("SESSION_S3_BUCKET")
    if settings.vector_store_provider == "pgvector":
        if not settings.pgvector_password:
            missing.append("PGVECTOR_PASSWORD")
    if missing:
        raise RuntimeError(f"缺失环境变量: {', '.join(missing)}")
    return (
        f"LLM={settings.llm_provider}:{settings.llm_model}, "
        f"Embedder={settings.embedder_provider}:{settings.embedder_model} "
        f"(dims={settings.embedder_dims}), "
        f"VectorStore={settings.vector_store_provider}, "
        f"Session={settings.session_backend}"
    )


def check_llm() -> str:
    """调 LLM 一次简单 completion。"""
    from agents.memory_agent import build_model

    model = build_model()
    # Strands Model 接口: stream_messages / converse。测试用最简 API
    # 通过 Agent 单轮调用更稳(避免版本差异)
    from strands import Agent
    agent = Agent(model=model, system_prompt="You are a test bot.")
    resp = agent('回复 "pong" 两个字')
    text = str(resp).strip()
    if not text:
        raise RuntimeError("LLM 返回空")
    return f"返回长度 {len(text)} 字符"


def check_embedder() -> str:
    """让 Mem0 embedder 对一句话向量化,并核对维度。"""
    from mem0.utils.factory import EmbedderFactory
    from config.mem0_config import build_mem0_embedder_config

    cfg = build_mem0_embedder_config()
    embedder = EmbedderFactory.create(cfg["provider"], cfg["config"], vector_config=None)
    vec = embedder.embed("hello world")
    if not isinstance(vec, list) or len(vec) != settings.embedder_dims:
        raise RuntimeError(
            f"向量维度不匹配: 实际 {len(vec) if isinstance(vec, list) else '?'}, "
            f"配置 {settings.embedder_dims}"
        )
    return f"向量维度 {len(vec)} ✓"


def check_s3() -> str:
    """Session bucket 读写 + 清理。"""
    if settings.session_backend != "s3":
        return "跳过 (SESSION_BACKEND != s3)"

    s3 = boto3.client("s3", region_name=settings.aws_region)
    key = f"{settings.session_s3_prefix}_healthcheck_{uuid.uuid4().hex}.txt"
    body = f"ok {datetime.utcnow().isoformat()}"
    s3.put_object(Bucket=settings.session_s3_bucket, Key=key, Body=body.encode())
    obj = s3.get_object(Bucket=settings.session_s3_bucket, Key=key)
    got = obj["Body"].read().decode()
    s3.delete_object(Bucket=settings.session_s3_bucket, Key=key)
    if got != body:
        raise RuntimeError(f"S3 读写内容不一致: {got!r} != {body!r}")
    return f"bucket={settings.session_s3_bucket}"


def check_pgvector() -> str:
    """Aurora PG 连通 + pgvector 扩展。"""
    if settings.vector_store_provider != "pgvector":
        return "跳过 (VECTOR_STORE_PROVIDER != pgvector)"

    import psycopg

    conn_str = (
        f"host={settings.pgvector_host} port={settings.pgvector_port} "
        f"dbname={settings.pgvector_dbname} user={settings.pgvector_user} "
        f"password={settings.pgvector_password} sslmode={settings.pgvector_sslmode}"
    )
    with psycopg.connect(conn_str, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            pg_ver = cur.fetchone()[0].split(",")[0]
            cur.execute("SELECT extname, extversion FROM pg_extension WHERE extname='vector'")
            row = cur.fetchone()
            if not row:
                raise RuntimeError(
                    "pgvector 扩展未安装。请先跑 infrastructure/pgvector_bootstrap.sql"
                )
            return f"{pg_ver}, pgvector={row[1]}"


def check_mem0_end_to_end() -> str:
    """Mem0: 写入 -> 检索 -> 清理。"""
    from memory.long_term import LongTermMemory

    ltm = LongTermMemory()
    user_id = f"_healthcheck_{uuid.uuid4().hex[:8]}"

    add_result = ltm.add(
        messages="I love TypeScript and dislike coriander.",
        user_id=user_id,
    )
    events = (
        add_result.get("results", []) if isinstance(add_result, dict) else []
    )

    search_result = ltm.search(
        query="What language does the user like?",
        user_id=user_id,
        limit=3,
        threshold=0.0,
    )
    if not search_result:
        raise RuntimeError(
            f"add 成功({len(events)} 条),但 search 无命中。"
            "可能是维度不匹配或 embedder 服务异常。"
        )
    top = search_result[0]

    # 清理
    ltm.delete_all(user_id=user_id)

    return (
        f"add={len(events)} 条, top-1 命中: "
        f"{top.get('memory', '?')!r} (score={top.get('score')})"
    )


def check_strands_agent() -> str:
    """Strands Agent 完整闭环: 建 agent -> 一轮对话 -> 清理 session。"""
    from agents import build_memory_agent
    from memory.session import build_session_manager

    session_id = f"_healthcheck_{uuid.uuid4().hex[:8]}"
    user_id = f"_healthcheck_user_{uuid.uuid4().hex[:8]}"

    agent = build_memory_agent(session_id=session_id, user_id=user_id)
    resp = agent('请只回复 "validated" 这一个词。')
    text = str(resp).strip()

    # 清理 session (S3/File)
    try:
        sm = build_session_manager(session_id)
        sm.delete_session(session_id)
    except Exception:
        pass

    if not text:
        raise RuntimeError("Agent 返回空")
    return f"agent 返回: {text[:60]!r}"


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
CHECKS = [
    ("配置加载", check_config),
    ("LLM 调用", check_llm),
    ("Embedding 调用", check_embedder),
    ("S3 Session Bucket", check_s3),
    ("Aurora PG + pgvector", check_pgvector),
    ("Mem0 端到端 (add+search)", check_mem0_end_to_end),
    ("Strands Agent 闭环", check_strands_agent),
]


def main() -> int:
    print("=" * 60)
    print("StrandsAgent-Mem0 连通性校验")
    print("=" * 60 + "\n")

    passed = 0
    failed = 0
    for name, fn in CHECKS:
        ok = _step(name, fn)
        if ok:
            passed += 1
        else:
            failed += 1

    total = passed + failed
    color = GREEN if failed == 0 else RED
    print("=" * 60)
    print(f"{color}结果: {passed}/{total} 通过{RESET}")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
