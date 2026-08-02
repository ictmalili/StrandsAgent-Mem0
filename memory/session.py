"""短期记忆 —— 使用 Strands 内置的 Session/Conversation Manager。

- 对话上下文管理: SlidingWindowConversationManager（保留最近 N 条）
- 会话持久化: S3SessionManager（生产/AWS 中国区）或 FileSessionManager（本地）
"""
from __future__ import annotations

from typing import Optional

import boto3
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.session.file_session_manager import FileSessionManager
from strands.session.s3_session_manager import S3SessionManager
from strands.session.session_manager import SessionManager

from config.settings import settings


def build_session_manager(session_id: str) -> SessionManager:
    """按 settings.session_backend 选择合适的 SessionManager。

    - s3: S3SessionManager (AWS 中国区推荐)
    - file: FileSessionManager (本地开发)
    """
    backend = settings.session_backend

    if backend == "s3":
        if not settings.session_s3_bucket:
            raise ValueError(
                "SESSION_BACKEND=s3 但 SESSION_S3_BUCKET 未配置"
            )
        # 显式构造 boto3 Session 以确保中国区 region 生效
        boto_session = boto3.Session(region_name=settings.aws_region)
        return S3SessionManager(
            session_id=session_id,
            bucket=settings.session_s3_bucket,
            prefix=settings.session_s3_prefix,
            boto_session=boto_session,
            region_name=settings.aws_region,
        )

    if backend == "file":
        return FileSessionManager(
            session_id=session_id,
            storage_dir=settings.session_file_dir,
        )

    raise ValueError(f"未知的 SESSION_BACKEND: {backend}")


def build_conversation_manager(
    window_size: Optional[int] = None,
) -> SlidingWindowConversationManager:
    """对话窗口管理器 —— 保留最近 N 条消息进入 LLM 上下文。

    Strands 会自动裁剪超出窗口的旧消息，被裁掉的部分仍持久化在 SessionManager
    中（S3/File），不会丢失。
    """
    return SlidingWindowConversationManager(
        window_size=window_size or settings.conversation_window_size,
    )
