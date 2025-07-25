from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Core
    environment: str = "dev"
    debug: bool = False

    # Security
    secret_key: str = "change_me"
    token_expiry_minutes: int = 60 
    jwt_algorithm: str = "HS256"
   
    # LDAP Config
    ldap_server: str = "ldap://ldap.hpcl.co.in"
    ldap_domain: str = "HPCL"

    # DB / Cache
    db_url_test_main:str = ""
    db_url_test_logs:str = ""
    database_url: str = "sqlite+aiosqlite:///./test.db"
    redis_url: str = "redis://localhost:6379/0"


    # Logging / Monitoring
    log_cfg: str = "monitoring/logging/logging.yaml"
    prometheus_enabled: bool = True

    # Misc
    project_name: str = "fastapi-enterprise-clean"
    api_version_prefix: str = "/api/v1"

    timezone: str = "Asia/Kolkata"

    # Pydantic Settings Config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()
