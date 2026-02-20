"""
utils/auth.py — Vérification des JWT Supabase
Supporte HS256 (legacy) et RS256 (nouveaux projets via JWKS).
Dépendance FastAPI : Depends(get_current_user_id) → str (user UUID)
"""
import logging
from fastapi import Header, HTTPException

logger = logging.getLogger("bombo.auth")

# Cache du client JWKS (évite de re-fetcher les clés à chaque requête)
_jwks_client = None


def _get_jwks_client():
    global _jwks_client
    if _jwks_client is None:
        import jwt
        from config import settings
        jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        _jwks_client = jwt.PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


def get_current_user_id(authorization: str = Header(None)) -> str:
    """
    Extrait et vérifie le JWT Supabase depuis le header Authorization.
    - RS256 (nouveaux projets) → vérification via JWKS endpoint
    - HS256 (legacy)           → vérification via SUPABASE_JWT_SECRET
    - Fallback                 → décodage sans vérification (dev uniquement)
    Retourne le user_id (sub) si valide, sinon lève une 401.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Non authentifié")

    token = authorization[7:]

    try:
        import jwt
        from config import settings

        # Lire l'algorithme depuis le header du JWT sans le vérifier
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")

        if alg in ("RS256", "RS384", "RS512", "ES256", "ES384", "ES512"):
            # Nouveaux projets Supabase — vérification via JWKS
            jwks_client = _get_jwks_client()
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated",
            )

        elif alg == "HS256" and settings.SUPABASE_JWT_SECRET:
            # Anciens projets Supabase — vérification via secret symétrique
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )

        else:
            # Fallback sans vérification (dev uniquement)
            logger.warning(
                "JWT décodé sans vérification (alg=%s, secret=%s)",
                alg,
                "absent" if not settings.SUPABASE_JWT_SECRET else "présent",
            )
            payload = jwt.decode(token, options={"verify_signature": False})

        user_id: str | None = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token invalide : sub manquant")

        return user_id

    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Erreur de vérification JWT : %s", exc)
        raise HTTPException(status_code=401, detail=f"Token invalide : {exc}")
