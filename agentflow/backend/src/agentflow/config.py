"""
AgentFlow settings loaded from environment variables.
Uses pydantic-settings for type-safe, documented config.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_BACKEND_DIR / ".env", _ROOT_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    #  LLM providers
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    moonshot_api_key: str = Field(default="", alias="MOONSHOT_API_KEY")
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_api_key_backup: str = Field(default="", alias="OPENROUTER_API_KEY_BACKUP")
    openrouter_api_key_tertiary: str = Field(default="", alias="OPENROUTER_API_KEY_TERTIARY")

    def get_openrouter_api_keys(self) -> list[str]:
        """Return ordered list of available OpenRouter API keys (primary -> secondary -> tertiary)."""
        keys: list[str] = []
        for raw in (self.openrouter_api_key, self.openrouter_api_key_backup, self.openrouter_api_key_tertiary):
            if raw:
                for k in raw.split(","):
                    k_clean = k.strip()
                    if k_clean and k_clean not in keys:
                        keys.append(k_clean)
        return keys

    # Default model used by agents when no model is specified in node config.
 
    default_model: str = Field(default="openrouter/free", alias="DEFAULT_MODEL")
    mock_llm: bool = Field(default=False, alias="MOCK_LLM")
    simulation_mode: bool = Field(default=False, alias="AGENTFLOW_SIMULATION_MODE")

    # Database (Phase 4+) 
    database_url: str = Field(
        default="postgresql+asyncpg://agentflow:agentflow@localhost:5432/agentflow",
        alias="DATABASE_URL",
    )

    # Redis / Arq (Phase 4+) 
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Security 
    secret_key: str = Field(default="CHANGE_ME_IN_PRODUCTION", alias="SECRET_KEY")
    fernet_key: str = Field(default="", alias="FERNET_KEY")

    # Execution limits 
    default_node_timeout_seconds: int = Field(default=120, alias="DEFAULT_NODE_TIMEOUT_SECONDS")
    default_max_steps: int = Field(default=100, alias="DEFAULT_MAX_STEPS")
    default_max_cost_usd: float = Field(default=5.0, alias="DEFAULT_MAX_COST_USD")

    # Logging 
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="console", alias="LOG_FORMAT")  # "json" | "console"


settings = Settings()
