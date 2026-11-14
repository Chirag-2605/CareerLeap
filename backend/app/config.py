
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    auth_required: bool = True
    max_upload_mb: int = 8
    cors_origins: str = "http://localhost:8081"
    firebase_service_account_json: Optional[str] = None
    database_url: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
