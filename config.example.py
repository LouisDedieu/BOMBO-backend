"""
config.py - Configuration de l'application BOMBO

Ce fichier doit être copié depuis votre projet existant.
Si vous n'en avez pas, voici un exemple de configuration.
"""
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration de l'application"""

    # ── ML Configuration ──────────────────────────────────────────────────
    MODEL_ID: str = "Qwen/Qwen2-VL-7B-Instruct"
    MAX_PIXELS: int = 360 * 420  # Résolution max pour les frames vidéo
    FPS: float = 1.0  # Frames par seconde à extraire
    MAX_NEW_TOKENS: int = 4096  # Tokens max pour la génération

    # ── Server Configuration ──────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── Supabase Configuration ────────────────────────────────────────────
    # IMPORTANT: Utilisez la clé service_role, PAS la clé anon
    # Trouvez-la dans : Supabase Dashboard → Settings → API → service_role key
    supabase_url: Optional[str] = None
    supabase_service_key: Optional[str] = None

    # ── Video Download Configuration ──────────────────────────────────────
    # Fichier de cookies pour yt-dlp (optionnel, pour les vidéos privées)
    COOKIES_FILE: Optional[str] = None

    # Proxy pour yt-dlp (optionnel, utile si votre IP est bloquée)
    # Format: "http://proxy:port" ou "socks5://proxy:port"
    PROXY_URL: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Instance globale des settings
settings = Settings()


# ── Exemple de fichier .env ──────────────────────────────────────────────
"""
# .env - Variables d'environnement (ne pas committer ce fichier!)

# ML Configuration
MODEL_ID=Qwen/Qwen2-VL-7B-Instruct
MAX_PIXELS=151200
FPS=1.0
MAX_NEW_TOKENS=4096

# Server
HOST=0.0.0.0
PORT=8000

# Supabase (optionnel)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJhbG...your-service-role-key-here

# Video Download (optionnel)
COOKIES_FILE=/path/to/cookies.txt
PROXY_URL=http://your-proxy:8080
"""
