"""统一配置加载。从环境变量 / .env 读取，暴露为 pydantic 模型。"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


# 支持的 LLM Provider:
#   国内 (OpenAI 兼容): deepseek | qwen | zhipu | openai_compatible
#   海外:               openai (直连) | bedrock (Amazon Bedrock, 需海外区)
LLMProvider = Literal[
    "deepseek", "qwen", "zhipu", "openai_compatible", "openai", "bedrock"
]

# 支持的 Embedding Provider:
#   国内: qwen | zhipu | openai_compatible
#   海外: openai | bedrock
EmbedderProvider = Literal[
    "qwen", "zhipu", "openai_compatible", "openai", "bedrock"
]

VectorStoreProvider = Literal["pgvector", "opensearch"]
OpenSearchAuthType = Literal["basic", "aws_iam"]
SessionBackend = Literal["s3", "file"]


class Settings(BaseSettings):
    """全局配置对象。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- LLM ----------
    llm_provider: LLMProvider = "bedrock"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 2048
    # Bedrock 专用: 模型调用区域 (可与数据面 aws_region 不同)
    bedrock_region: str = "us-east-1"

    # ---------- Embedder ----------
    embedder_provider: EmbedderProvider = "bedrock"
    embedder_api_key: str = ""
    embedder_base_url: str = ""
    embedder_model: str = "amazon.titan-embed-text-v2:0"
    embedder_dims: int = 1024

    # ---------- AWS (数据面: S3 + Aurora + OpenSearch) ----------
    aws_region: str = "cn-northwest-1"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None

    # ---------- 短期记忆 (Session) ----------
    session_backend: SessionBackend = "s3"
    session_s3_bucket: str = ""
    session_s3_prefix: str = "sessions/"
    session_file_dir: str = "./.sessions"
    conversation_window_size: int = 20

    # ---------- 长期记忆 (向量库) ----------
    vector_store_provider: VectorStoreProvider = "pgvector"

    # pgvector / Aurora PostgreSQL
    pgvector_host: str = "localhost"
    pgvector_port: int = 5432
    pgvector_user: str = "postgres"
    pgvector_password: str = ""
    pgvector_dbname: str = "mem0"
    pgvector_collection: str = "memories"
    pgvector_sslmode: str = "require"
    pgvector_use_hnsw: bool = True

    # OpenSearch (可选)
    opensearch_host: str = "localhost"
    opensearch_port: int = 9200
    opensearch_use_ssl: bool = True
    opensearch_verify_certs: bool = True
    opensearch_auth_type: OpenSearchAuthType = "basic"
    opensearch_user: str = "admin"
    opensearch_password: str = ""
    opensearch_index: str = "mem0_memories"


settings = Settings()
