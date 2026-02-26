"""Application settings loaded from environment."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized runtime configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    db_host: str = Field(default="127.0.0.1", alias="DB_HOST")
    db_port: int = Field(default=3306, alias="DB_PORT")
    db_name: str = Field(default="smc_trading", alias="DB_NAME")
    db_user: str = Field(default="smc_user", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")
    db_pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW")
    db_echo: bool = Field(default=False, alias="DB_ECHO")

    retention_days: int = Field(default=365, alias="RETENTION_DAYS")
    batch_size: int = Field(default=1000, alias="BATCH_SIZE")

    dukascopy_rate_limit_ms: int = Field(default=250, alias="DUKASCOPY_RATE_LIMIT_MS")
    binance_rate_limit_ms: int = Field(default=250, alias="BINANCE_RATE_LIMIT_MS")

    @property
    def mysql_dsn(self) -> str:
        """Build SQLAlchemy DSN without exposing secrets in logs."""
        return (
            "mysql+pymysql://"
            f"{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a singleton settings instance."""
    return Settings()
