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
    lala_cors_origins: str = Field(
        default="http://localhost:3001,http://localhost:3002",
        validation_alias="LALA_CORS_ORIGINS",
    )
    lala_default_timezone: str = Field(default="Asia/Kolkata", validation_alias="LALA_DEFAULT_TIMEZONE")
    lala_integration_key_pepper: str = Field(
        default="", validation_alias="LALA_INTEGRATION_KEY_PEPPER"
    )
    # Epic 7 — voice transcript/recording retention (D01 recommended default: 90 days).
    voice_retention_days: int = Field(default=90, validation_alias="LALA_VOICE_RETENTION_DAYS")

    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    google_client_id: str = Field(default="", validation_alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", validation_alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(
        default="http://localhost:8000/v1/calendar/google/callback",
        validation_alias="GOOGLE_REDIRECT_URI",
    )
    calcom_api_key: str = Field(default="", validation_alias="CALCOM_API_KEY")
    calcom_webhook_secret: str = Field(default="", validation_alias="CALCOM_WEBHOOK_SECRET")
    lala_visitor_session_secret: str = Field(
        default="", validation_alias="LALA_VISITOR_SESSION_SECRET"
    )

    # Epic 6 — server only. Never expose via NEXT_PUBLIC_*.
    gnani_api_key: str = Field(default="", validation_alias="GNANI_API_KEY")
    gnani_api_base_url: str = Field(
        default="https://api.vachana.ai", validation_alias="GNANI_API_BASE_URL"
    )
    gnani_stt_model: str = Field(default="prisma-v3.0", validation_alias="GNANI_STT_MODEL")
    gnani_tts_model: str = Field(default="timbre-v2.5", validation_alias="GNANI_TTS_MODEL")
    gnani_tts_voice_en: str = Field(default="Kaveri", validation_alias="GNANI_TTS_VOICE_EN")
    gnani_tts_voice_hi: str = Field(default="Nalini", validation_alias="GNANI_TTS_VOICE_HI")
    gnani_tts_voice_te: str = Field(default="Kaveri", validation_alias="GNANI_TTS_VOICE_TE")

    # OpenAI-compatible chat API. Preferred POC brain: OpenRouter (see .env.example).
    # Self-hosted Evon (vLLM/SGLang) still works with the same fields.
    llm_base_url: str = Field(default="", validation_alias="LLM_BASE_URL")
    llm_model: str = Field(default="openai/gpt-4o-mini", validation_alias="LLM_MODEL")
    llm_api_key: str = Field(default="", validation_alias="LLM_API_KEY")
    # Optional alias — if LLM_API_KEY is empty, OpenRouter key is used.
    openrouter_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    # Preferred HF repo ID if using self-hosted Evon instead of OpenAI.
    evon_hf_repo_id: str = Field(
        default="gnani/gnani-evon-v3.3-30B-A3B", validation_alias="EVON_HF_REPO_ID"
    )

    @property
    def cors_origins(self) -> List[str]:
        return [item.strip() for item in self.lala_cors_origins.split(",") if item.strip()]

    @property
    def gnani_configured(self) -> bool:
        return bool(self.gnani_api_key.strip()) and not self.gnani_api_key.strip().startswith("PASTE_")

    @property
    def llm_provider(self) -> str:
        """Logical brain provider for status badges / docs."""
        base = self.llm_base_url.strip().lower()
        if not base:
            return "none"
        if "openrouter.ai" in base:
            return "openrouter"
        if "openai.com" in base:
            return "openai"
        if "gnani" in self.llm_model.lower() or "evon" in self.llm_model.lower():
            return "evon"
        return "openai_compatible"

    @property
    def resolved_llm_api_key(self) -> str:
        primary = self.llm_api_key.strip()
        if primary:
            return primary
        return self.openrouter_api_key.strip()

    @property
    def llm_configured(self) -> bool:
        if not self.llm_base_url.strip():
            return False
        key = self.resolved_llm_api_key
        # Hosted APIs need a real key. Self-hosted Evon may omit one.
        if self.llm_provider in {"openai", "openrouter"}:
            return bool(key) and not key.startswith("PASTE_") and key != "sk-your-key"
        return True

    @property
    def google_calendar_configured(self) -> bool:
        return bool(self.google_client_id.strip() and self.google_client_secret.strip())

    @property
    def calcom_configured(self) -> bool:
        return bool(self.calcom_webhook_secret.strip())

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url.strip())

    @property
    def visitor_session_pepper(self) -> str:
        explicit = self.lala_visitor_session_secret.strip()
        if explicit:
            return explicit
        return self.lala_integration_key_pepper.strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
