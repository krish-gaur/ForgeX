"""Centralized configuration for the ForgeX backend (pydantic-settings, .env driven)."""
from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]  # ForgeX/backend


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False)

    # -- app ------------------------------------------------------------------
    app_name: str = "ForgeX"
    environment: str = "development"  # development | production | test
    log_level: str = "INFO"
    base_path: Path = BASE_DIR
    data_dir: Path = BASE_DIR / "data"
    file_store_dir: Path = BASE_DIR / "data" / "files"
    dataset_dir: Path = BASE_DIR.parent / "datasets"
    template_dir: Path = BASE_DIR / "templates"

    # -- security -------------------------------------------------------------
    secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60
    refresh_token_ttl_days: int = 7
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    trusted_proxy: bool = False

    # -- database -------------------------------------------------------------
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'forgex.db'}"
    auto_create_schema: bool = True  # dev convenience; Alembic remains canonical

    # -- execution ------------------------------------------------------------
    collector_timeout_sec: int = 30
    script_timeout_sec: int = 30
    task_backend: str = "inline"  # inline | celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    max_concurrent_jobs: int = 3

    # -- graph / vector -------------------------------------------------------
    graph_store: str = "sql"  # sql | neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    embedding_provider: str = "local"  # local | openai
    embedding_dim: int = 256

    # -- AI -------------------------------------------------------------------
    llm_provider: str = "auto"  # auto | anthropic | openai | off
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_model_anthropic: str = "claude-sonnet-4-6"
    llm_model_openai: str = "gpt-4o"
    llm_timeout_sec: int = 45

    # -- blockchain anchoring -------------------------------------------------
    blockchain_anchor: str = "local"  # local | sepolia
    sepolia_rpc_url: str = ""
    sepolia_private_key: str = ""

    # -- rate limits ----------------------------------------------------------
    rate_limit_api_per_min: int = 100
    rate_limit_fql_per_hour: int = 20
    rate_limit_login_per_min: int = 10

    # -- demo -----------------------------------------------------------------
    demo_seed_on_boot: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def model_post_init(self, __context) -> None:  # noqa: D105
        if not self.secret_key:
            # Dev-only ephemeral key; production must set FORGEX-free env SECRET_KEY.
            object.__setattr__(self, "secret_key", secrets.token_hex(32))
        if self.is_production and len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters in production")
        for d in (self.data_dir, self.file_store_dir):
            Path(d).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
