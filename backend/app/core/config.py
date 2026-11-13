from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    supabase_jwt_secret: str = Field(default="", validation_alias="SUPABASE_JWT_SECRET")
    supabase_url: str = Field(default="", validation_alias="SUPABASE_URL")
    lala_cors_origins: str = Field(default="http://localhost:3001", validation_alias="LALA_CORS_ORIGINS")
    lala_default_timezone: str = Field(default="Asia/Kolkata", validation_alias="LALA_DEFAULT_TIMEZONE")

    @property
    def cors_origins(self) -> List[str]:
        return [item.strip() for item in self.lala_cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
