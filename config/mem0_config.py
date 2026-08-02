"""构造 Mem0 的初始化配置。

- LLM: 国内走 OpenAI 兼容路径 (DeepSeek/Qwen/GLM), 海外可选 OpenAI 直连或 Bedrock
- Embedder: 同上, Bedrock 用 Titan
- Vector Store: 默认 pgvector (Aurora PG), 可选 opensearch
"""
from __future__ import annotations

from typing import Any, Dict

from .settings import settings


_OPENAI_COMPATIBLE_URLS = {
    "deepseek": "https://api.deepseek.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "openai": "https://api.openai.com/v1",
}

# 走 OpenAI 兼容协议的 Provider (Mem0 用 provider="openai")
_OPENAI_STYLE_PROVIDERS = {
    "deepseek", "qwen", "zhipu", "openai_compatible", "openai"
}


def _resolve_base_url(provider: str, configured: str) -> str:
    return configured or _OPENAI_COMPATIBLE_URLS.get(provider, "")


# --------------------------------------------------------------------------- #
# LLM
# --------------------------------------------------------------------------- #
def build_mem0_llm_config() -> Dict[str, Any]:
    provider = settings.llm_provider

    if provider in _OPENAI_STYLE_PROVIDERS:
        return {
            "provider": "openai",
            "config": {
                "model": settings.llm_model,
                "openai_base_url": _resolve_base_url(provider, settings.llm_base_url),
                "api_key": settings.llm_api_key,
                "temperature": settings.llm_temperature,
                "max_tokens": settings.llm_max_tokens,
            },
        }

    if provider == "bedrock":
        return {
            "provider": "aws_bedrock",
            "config": {
                "model": settings.llm_model,   # e.g. anthropic.claude-sonnet-4-...
                "aws_region": settings.bedrock_region,
                "temperature": settings.llm_temperature,
                "max_tokens": settings.llm_max_tokens,
            },
        }

    raise ValueError(f"未知的 LLM_PROVIDER: {provider}")


# --------------------------------------------------------------------------- #
# Embedder
# --------------------------------------------------------------------------- #
def build_mem0_embedder_config() -> Dict[str, Any]:
    provider = settings.embedder_provider

    if provider in _OPENAI_STYLE_PROVIDERS:
        return {
            "provider": "openai",
            "config": {
                "model": settings.embedder_model,
                "openai_base_url": _resolve_base_url(provider, settings.embedder_base_url),
                "api_key": settings.embedder_api_key,
                "embedding_dims": settings.embedder_dims,
            },
        }

    if provider == "bedrock":
        return {
            "provider": "aws_bedrock",
            "config": {
                "model": settings.embedder_model,  # e.g. amazon.titan-embed-text-v2:0
                "aws_region": settings.bedrock_region,
                "embedding_dims": settings.embedder_dims,
            },
        }

    raise ValueError(f"未知的 EMBEDDER_PROVIDER: {provider}")


# --------------------------------------------------------------------------- #
# Vector Store
# --------------------------------------------------------------------------- #
def _build_pgvector_config() -> Dict[str, Any]:
    return {
        "provider": "pgvector",
        "config": {
            "user": settings.pgvector_user,
            "password": settings.pgvector_password,
            "host": settings.pgvector_host,
            "port": settings.pgvector_port,
            "dbname": settings.pgvector_dbname,
            "collection_name": settings.pgvector_collection,
            "embedding_model_dims": settings.embedder_dims,
            "sslmode": settings.pgvector_sslmode,
            "hnsw": settings.pgvector_use_hnsw,
        },
    }


def _build_opensearch_config() -> Dict[str, Any]:
    vs_cfg: Dict[str, Any] = {
        "collection_name": settings.opensearch_index,
        "host": settings.opensearch_host,
        "port": settings.opensearch_port,
        "embedding_model_dims": settings.embedder_dims,
        "use_ssl": settings.opensearch_use_ssl,
        "verify_certs": settings.opensearch_verify_certs,
    }
    if settings.opensearch_auth_type == "basic":
        vs_cfg["http_auth"] = (
            settings.opensearch_user, settings.opensearch_password
        )
    else:
        from requests_aws4auth import AWS4Auth
        import boto3
        credentials = boto3.Session(region_name=settings.aws_region).get_credentials()
        vs_cfg["http_auth"] = AWS4Auth(
            credentials.access_key, credentials.secret_key,
            settings.aws_region, "es",
            session_token=credentials.token,
        )
    return {"provider": "opensearch", "config": vs_cfg}


def build_mem0_vector_store_config() -> Dict[str, Any]:
    provider = settings.vector_store_provider
    if provider == "pgvector":
        return _build_pgvector_config()
    if provider == "opensearch":
        return _build_opensearch_config()
    raise ValueError(f"未知的 VECTOR_STORE_PROVIDER: {provider}")


def build_mem0_config() -> Dict[str, Any]:
    return {
        "llm": build_mem0_llm_config(),
        "embedder": build_mem0_embedder_config(),
        "vector_store": build_mem0_vector_store_config(),
        "version": "v1.1",
    }
