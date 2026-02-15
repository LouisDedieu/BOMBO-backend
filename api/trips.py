"""
Routes pour la gestion des trips (voyages)
"""
import logging
from typing import List, Dict
from fastapi import APIRouter, HTTPException

from services.supabase_service import SupabaseService

logger = logging.getLogger("bombo.api.trips")

router = APIRouter(prefix="/trips", tags=["trips"])

# Instance globale du service Supabase (sera configurée au démarrage)
_supabase_service: SupabaseService = None


def set_supabase_service(service: SupabaseService):
    """Configure le service Supabase (appelé au démarrage de l'app)"""
    global _supabase_service
    _supabase_service = service


@router.get("/{trip_id}")
async def get_trip(trip_id: str) -> Dict:
    """Récupère les détails d'un voyage par son ID"""
    if not _supabase_service or not _supabase_service.is_configured():
        raise HTTPException(503, detail="Supabase non configuré")

    trip = await _supabase_service.get_trip(trip_id)
    if not trip:
        raise HTTPException(404, detail="Voyage introuvable")

    return trip


@router.get("/user/{user_id}")
async def get_user_trips(user_id: str) -> List[Dict]:
    """Récupère tous les voyages d'un utilisateur"""
    if not _supabase_service or not _supabase_service.is_configured():
        raise HTTPException(503, detail="Supabase non configuré")

    trips = await _supabase_service.get_user_trips(user_id)
    return trips
