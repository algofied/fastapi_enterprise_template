from __future__ import annotations

from functools import lru_cache
from typing import Optional, List, Dict, Any

from pydantic import Field, SecretStr, AnyUrl, field_validator
from pydantic_settings import BaseSettings as PydanticBaseSettings, SettingsConfigDict


# ---- Base (prod-safe) settings: NO env_file here ----
class Settings(PydanticBaseSettings):
    # Environment
    environment: str = Field(default="dev", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    service_name: str = Field(default="fastapi-enterprise-template", env="SERVICE_NAME")

    # Security / JWT
    secret_key: SecretStr = Field(..., env="SECRET_KEY")
    token_expiry_minutes: int = Field(default=60, env="TOKEN_EXPIRY_MINUTES")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")

    # LDAP
    ldap_server: str = Field(default="ldap://example.org", env="LDAP_SERVER")
    ldap_domain: str = Field(default="", env="LDAP_DOMAIN")

    # Databases / Cache (examples; prefer DSN from env)
    database_url: str = Field(..., env="DATABASE_URL")
    redis_url: Optional[str] = Field(default=None, env="REDIS_URL")
    db_url_test_main: str = Field(default="", env="DB_URL_TEST_MAIN")
    db_url_test_logs: str = Field(default="", env="DB_URL_TEST_LOGS")

    # Logging (consumed by your logger module)
    logs_timezone: str = Field(default="Asia/Kolkata", env="LOGS_TIMEZONE")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    log_to_stdout: bool = Field(default=True, env="LOG_TO_STDOUT")
    log_to_file: bool = Field(default=False, env="LOG_TO_FILE")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_exclude_paths: str = Field(default="", env="LOG_EXCLUDE_PATHS")
    log_dir: str = Field(default="/var/log/lims", env="LOG_DIR")
    access_log_file: str = Field(default="access.log", env="ACCESS_LOG_FILE")
    error_log_file: str = Field(default="error.log", env="ERROR_LOG_FILE")
    log_file_strategy: str = Field(default="rotating", env="LOG_FILE_STRATEGY")
    log_max_mb: int = Field(default=50, env="LOG_MAX_MB")
    log_backups: int = Field(default=10, env="LOG_BACKUPS")
    log_wire_sqlalchemy: bool = Field(default=False, env="LOG_WIRE_SQLALCHEMY")
    log_sqlalchemy_level: str = Field(default="WARNING", env="LOG_SQLALCHEMY_LEVEL")

    # Loki / DB / MinIO log sinks
    loki_enable: bool = Field(default=False, env="LOKI_ENABLE")
    loki_url: Optional[str] = Field(default=None, env="LOKI_URL")
    loki_labels: str = Field(default="job=lims", env="LOKI_LABELS")
    loki_timeout_s: int = Field(default=3, env="LOKI_TIMEOUT_S")

    log_db_enable: bool = Field(default=False, env="LOG_DB_ENABLE")
    log_db_url: Optional[str] = Field(default=None, env="LOG_DB_URL")
    log_db_table: str = Field(default="app_logs", env="LOG_DB_TABLE")

    minio_enable: bool = Field(default=False, env="MINIO_ENABLE")
    minio_endpoint: str = Field(default="minio:9000", env="MINIO_ENDPOINT")
    minio_secure: bool = Field(default=False, env="MINIO_SECURE")
    minio_access_key: Optional[SecretStr] = Field(default=None, env="MINIO_ACCESS_KEY")
    minio_secret_key: Optional[SecretStr] = Field(default=None, env="MINIO_SECRET_KEY")
    minio_bucket: str = Field(default="service-logs", env="MINIO_BUCKET")
    minio_flush_lines: int = Field(default=100, env="MINIO_FLUSH_LINES")
    minio_flush_secs: int = Field(default=5, env="MINIO_FLUSH_SECS")

    # API / App
    project_name: str = Field(default="fastapi-enterprise-clean", env="PROJECT_NAME")
    api_version_prefix: str = Field(default="/api/v1", env="API_VERSION_PREFIX")
    timezone: str = Field(default="Asia/Kolkata", env="TIMEZONE")

    # Pydantic model config (no .env here)
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("log_level")
    @classmethod
    def _normalize_level(cls, v: str) -> str:
        return v.upper().strip()

    def logging_defaults(self) -> Dict[str, Any]:
        return {
            "service": self.service_name,
            "environment": self.environment,
            "format": self.log_format,
            "to_stdout": self.log_to_stdout,
            "to_file": self.log_to_file,
            "level": self.log_level,
            "exclude_paths": [p.strip() for p in self.log_exclude_paths.split(",") if p.strip()],
            "file_strategy": self.log_file_strategy,
            "max_mb": self.log_max_mb,
            "backups": self.log_backups,
            "log_dir": self.log_dir,
            "access_log_file": self.access_log_file,
            "error_log_file": self.error_log_file,
            "wire_sqla": self.log_wire_sqlalchemy,
            "sqla_level": self.log_sqlalchemy_level,
            "loki": {
                "enable": self.loki_enable,
                "url": self.loki_url,
                "labels": self.loki_labels,
                "timeout_s": self.loki_timeout_s,
            },
            "db_sink": {
                "enable": self.log_db_enable,
                "url": self.log_db_url,
                "table": self.log_db_table,
            },
            "minio": {
                "enable": self.minio_enable,
                "endpoint": self.minio_endpoint,
                "secure": self.minio_secure,
                "access_key": self.minio_access_key.get_secret_value() if self.minio_access_key else None,
                "secret_key": self.minio_secret_key.get_secret_value() if self.minio_secret_key else None,
                "bucket": self.minio_bucket,
                "flush_lines": self.minio_flush_lines,
                "flush_secs": self.minio_flush_secs,
            },
        }


# ---- Dev convenience (local-only): WITH .env ----
class DevSettings(Settings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


def _choose_settings_class() -> type[Settings]:
    import os
    env = os.getenv("ENVIRONMENT", "prod").lower()
    return DevSettings if env in {"dev", "local"} else Settings


@lru_cache
def get_settings() -> Settings:
    return _choose_settings_class()()
