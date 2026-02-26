from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "limiq-io-api"
    app_env: str = "development"
    app_port: int = 8000

    postgres_user: str = "kya"
    postgres_password: str = "kya"
    postgres_db: str = "kya"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    kya_jwt_private_key_pem: str | None = None
    kya_jwt_public_key_pem: str | None = None
    kya_jwt_kid: str | None = None
    kya_workspace_bootstrap_token: str | None = None

    jwt_leeway_seconds: int = 5
    capability_default_ttl_minutes: int = 15
    capability_min_ttl_minutes: int = 5
    capability_max_ttl_minutes: int = 30

    rate_limit_window_seconds: int = 60
    rate_limit_redis_key_ttl_seconds: int = 70
    rate_limit_redis_fail_open: bool = False

    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle_seconds: int = 1800

    log_level: str = "INFO"

    audit_export_max_rows: int = 10000
    cors_allow_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR / ".env"), ".env"),
        env_file_encoding="utf-8",
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


settings = Settings()
