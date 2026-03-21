"""
api/cleanup.py – Endpoints de nettoyage de la base de données
Suppression automatique des comptes non vérifiés après X jours.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
import httpx

from config import settings
from models.errors import ErrorCode, ErrorResponse, get_error_message

logger = logging.getLogger("bombo.cleanup")

router = APIRouter(prefix="/cleanup", tags=["cleanup"])

# Clé secrète pour protéger l'endpoint (à configurer dans .env)
CLEANUP_SECRET_KEY: Optional[str] = getattr(settings, "CLEANUP_SECRET_KEY", None)


def verify_cleanup_auth(authorization: str = Header(None)) -> None:
    """
    Vérifie l'authentification pour les endpoints de cleanup.
    Accepte soit la clé secrète CLEANUP_SECRET_KEY, soit la clé service_role Supabase.
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail=ErrorResponse(
                error_code=ErrorCode.NOT_AUTHENTICATED,
                message="Authorization header required",
            ).model_dump(),
        )

    token = authorization.replace("Bearer ", "")

    # Vérifier si c'est la clé de cleanup ou la clé service_role
    valid_keys = [settings.SUPABASE_SERVICE_ROLE_KEY]
    if CLEANUP_SECRET_KEY:
        valid_keys.append(CLEANUP_SECRET_KEY)

    if token not in valid_keys:
        raise HTTPException(
            status_code=403,
            detail=ErrorResponse(
                error_code=ErrorCode.ACCESS_DENIED,
                message="Invalid cleanup authorization key",
            ).model_dump(),
        )


async def delete_unverified_users(days_old: int = 7, dry_run: bool = False) -> dict:
    """
    Supprime les utilisateurs non vérifiés créés il y a plus de X jours.

    Args:
        days_old: Nombre de jours après lesquels supprimer les comptes non vérifiés
        dry_run: Si True, ne supprime pas mais retourne les comptes qui seraient supprimés

    Returns:
        Dict avec le nombre de comptes supprimés et les détails
    """
    if not settings.supabase_url or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code=ErrorCode.UNKNOWN_ERROR,
                message="Supabase not configured",
            ).model_dump(),
        )

    # Calculer la date limite
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
    cutoff_iso = cutoff_date.isoformat()

    headers = {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }

    # URL de l'API Admin de Supabase
    admin_url = f"{settings.supabase_url}/auth/v1/admin/users"

    deleted_users = []
    page = 1
    per_page = 100

    async with httpx.AsyncClient() as client:
        while True:
            # Lister les utilisateurs (pagination)
            response = await client.get(
                admin_url,
                headers=headers,
                params={"page": page, "per_page": per_page},
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(f"Erreur listing users: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=500,
                    detail=ErrorResponse(
                        error_code=ErrorCode.UNKNOWN_ERROR,
                        message=f"Failed to list users: {response.text}",
                    ).model_dump(),
                )

            data = response.json()
            users = data.get("users", [])

            if not users:
                break

            for user in users:
                # Vérifier si l'utilisateur n'est pas vérifié ET créé avant la date limite
                email_confirmed = user.get("email_confirmed_at")
                created_at = user.get("created_at")

                if email_confirmed is None and created_at:
                    # Parser la date de création
                    try:
                        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        if created < cutoff_date:
                            user_info = {
                                "id": user.get("id"),
                                "email": user.get("email"),
                                "created_at": created_at,
                            }

                            if not dry_run:
                                # Supprimer l'utilisateur via l'API Admin
                                delete_response = await client.delete(
                                    f"{admin_url}/{user['id']}",
                                    headers=headers,
                                    timeout=10,
                                )
                                if delete_response.status_code in (200, 204):
                                    deleted_users.append(user_info)
                                    logger.info(f"Utilisateur supprimé: {user.get('email')} (créé le {created_at})")
                                else:
                                    logger.warning(
                                        f"Échec suppression {user.get('email')}: "
                                        f"{delete_response.status_code} - {delete_response.text}"
                                    )
                            else:
                                deleted_users.append(user_info)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Date invalide pour user {user.get('id')}: {e}")

            # Pagination
            if len(users) < per_page:
                break
            page += 1

    action = "would be deleted" if dry_run else "deleted"
    logger.info(f"Cleanup terminé: {len(deleted_users)} comptes non vérifiés {action}")

    return {
        "success": True,
        "dry_run": dry_run,
        "days_threshold": days_old,
        "cutoff_date": cutoff_iso,
        "users_deleted": len(deleted_users),
        "users": deleted_users if len(deleted_users) <= 100 else deleted_users[:100],
        "truncated": len(deleted_users) > 100,
    }


@router.post("/unverified-users")
async def cleanup_unverified_users(
    authorization: str = Header(None),
    days: int = Query(default=7, ge=1, le=365, description="Supprimer les comptes non vérifiés de plus de X jours"),
    dry_run: bool = Query(default=True, description="Si true, simule sans supprimer"),
):
    """
    Supprime les comptes utilisateurs non vérifiés créés il y a plus de X jours.

    - **days**: Nombre de jours (défaut: 7, min: 1, max: 365)
    - **dry_run**: Mode simulation (défaut: true) - passer false pour supprimer vraiment

    Authentification requise: CLEANUP_SECRET_KEY ou SUPABASE_SERVICE_ROLE_KEY dans le header Authorization.

    Exemple d'appel:
    ```
    curl -X POST "https://api.bombo.app/cleanup/unverified-users?days=7&dry_run=false" \
         -H "Authorization: Bearer YOUR_SECRET_KEY"
    ```
    """
    verify_cleanup_auth(authorization)
    return await delete_unverified_users(days_old=days, dry_run=dry_run)


@router.get("/unverified-users/stats")
async def get_unverified_users_stats(
    authorization: str = Header(None),
    days: int = Query(default=7, ge=1, le=365),
):
    """
    Retourne les statistiques des comptes non vérifiés (sans supprimer).
    Équivalent à POST avec dry_run=true.
    """
    verify_cleanup_auth(authorization)
    return await delete_unverified_users(days_old=days, dry_run=True)
