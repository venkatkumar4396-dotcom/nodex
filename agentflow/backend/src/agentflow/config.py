"""
AgentFlow settings loaded from environment variables.
Uses pydantic-settings for type-safe, documented config.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM providers ────────────────────────────────────────────────────────
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")

    # Kimi / Moonshot AI — use prefix "moonshot/" in model names
    # e.g. moonshot/moonshot-v1-32k, moonshot/kimi-k2.5
    moonshot_api_key: str = Field(default="", alias="MOONSHOT_API_KEY")

    # Default model used by agents when no model is specified in node config.
    # Examples:
    #   Kimi:      moonshot/moonshot-v1-32k  (recommended)
    #   OpenAI:    gpt-4o-mini
    #   Anthropic: claude-3-5-sonnet-20241022
    #   Gemini:    gemini/gemini-1.5-flash
    #   Ollama:    ollama/llama3
    default_model: str = Field(default="moonshot/moonshot-v1-32k", alias="DEFAULT_MODEL")

    # ── Database (Phase 4+) ───────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://agentflow:agentflow@localhost:5432/agentflow",
        alias="DATABASE_URL",
    )

    # ── Redis / Arq (Phase 4+) ────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # ── Security ──────────────────────────────────────────────────────────────
    secret_key: str = Field(default="CHANGE_ME_IN_PRODUCTION", alias="SECRET_KEY")
    fernet_key: str = Field(default="", alias="FERNET_KEY")

    # ── Execution limits ──────────────────────────────────────────────────────
    default_node_timeout_seconds: int = Field(default=120, alias="DEFAULT_NODE_TIMEOUT_SECONDS")
    default_max_steps: int = Field(default=100, alias="DEFAULT_MAX_STEPS")
    default_max_cost_usd: float = Field(default=5.0, alias="DEFAULT_MAX_COST_USD")

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="console", alias="LOG_FORMAT")  # "json" | "console"


settings = Settings()
