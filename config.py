"""
config.py — Paramètres centralisés BOMBO
Tous les knobs du modèle et du serveur en un seul endroit.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict  # ← add SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",       # silently drop unknown env vars
    )

    # ── Gemini API ────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL_ID: str = "gemini-2.0-flash"

    # ── Serveur ───────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── Téléchargement ────────────────────────────────────────────────────────
    COOKIES_FILE: str | None = None
    PROXY_URL: str | None = None
    DOWNLOAD_TIMEOUT: int = 120

    # ── Supabase ──────────────────────────────────────────────────────────────
    supabase_url: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""


settings = Settings()