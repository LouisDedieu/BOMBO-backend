"""
Configuration pytest et fixtures partagées pour les tests d'intégration.
"""
import os
import uuid
import pytest
from typing import Generator, Dict, Any
from supabase import create_client, Client

# ── Configuration ────────────────────────────────────────────────────────────

def get_test_supabase_client() -> Client | None:
    """
    Crée un client Supabase pour les tests d'intégration.
    Retourne None si les variables d'environnement ne sont pas configurées.
    """
    url = os.getenv("supabase_url") or os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        return None

    return create_client(url, key)


def generate_test_id(prefix: str = "test") -> str:
    """Génère un ID unique pour les tests."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def supabase_client() -> Generator[Client | None, None, None]:
    """
    Client Supabase pour les tests d'intégration.
    Skip les tests si non configuré.
    """
    client = get_test_supabase_client()
    yield client


@pytest.fixture
def skip_if_no_supabase(supabase_client):
    """Skip le test si Supabase n'est pas configuré."""
    if supabase_client is None:
        pytest.skip("Supabase non configuré (variables d'environnement manquantes)")


@pytest.fixture
def test_user_id() -> str:
    """ID utilisateur pour les tests (doit exister dans auth.users)."""
    # Utiliser un user ID de test fixe ou en créer un
    return os.getenv("TEST_USER_ID", "test-user-integration")


@pytest.fixture
def test_trip(supabase_client, test_user_id, skip_if_no_supabase) -> Generator[Dict[str, Any], None, None]:
    """
    Crée un trip de test et le supprime après le test.
    """
    trip_id = generate_test_id("trip")

    trip_data = {
        "id": trip_id,
        "user_id": test_user_id,
        "trip_title": "Test Integration Trip",
        "status": "draft",
    }

    # Créer le trip
    result = supabase_client.from_("trips").insert(trip_data).execute()

    if not result.data:
        pytest.skip("Impossible de créer le trip de test")

    yield result.data[0]

    # Cleanup: supprimer le trip et les données liées
    try:
        # Supprimer les spots liés aux jours du trip
        days = supabase_client.from_("itinerary_days").select("id").eq("trip_id", trip_id).execute()
        if days.data:
            day_ids = [d["id"] for d in days.data]
            supabase_client.from_("spots").delete().in_("itinerary_day_id", day_ids).execute()

        # Supprimer les jours
        supabase_client.from_("itinerary_days").delete().eq("trip_id", trip_id).execute()

        # Supprimer les destinations
        supabase_client.from_("destinations").delete().eq("trip_id", trip_id).execute()

        # Supprimer le trip
        supabase_client.from_("trips").delete().eq("id", trip_id).execute()
    except Exception as e:
        print(f"Cleanup error: {e}")


@pytest.fixture
def test_destination(supabase_client, test_trip, skip_if_no_supabase) -> Generator[Dict[str, Any], None, None]:
    """
    Crée une destination de test.
    """
    dest_id = generate_test_id("dest")

    dest_data = {
        "id": dest_id,
        "trip_id": test_trip["id"],
        "city": "Paris Test",
        "country": "France",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "visit_order": 1,
    }

    result = supabase_client.from_("destinations").insert(dest_data).execute()

    if not result.data:
        pytest.skip("Impossible de créer la destination de test")

    yield result.data[0]


@pytest.fixture
def test_day(supabase_client, test_trip, test_destination, skip_if_no_supabase) -> Generator[Dict[str, Any], None, None]:
    """
    Crée un jour d'itinéraire de test.
    """
    day_id = generate_test_id("day")

    day_data = {
        "id": day_id,
        "trip_id": test_trip["id"],
        "destination_id": test_destination["id"],
        "day_number": 1,
        "location": "Paris Test",
    }

    result = supabase_client.from_("itinerary_days").insert(day_data).execute()

    if not result.data:
        pytest.skip("Impossible de créer le jour de test")

    yield result.data[0]


@pytest.fixture
def test_spot(supabase_client, test_day, skip_if_no_supabase) -> Generator[Dict[str, Any], None, None]:
    """
    Crée un spot de test.
    """
    spot_id = generate_test_id("spot")

    spot_data = {
        "id": spot_id,
        "itinerary_day_id": test_day["id"],
        "name": "Test Spot",
        "spot_type": "attraction",  # Valeur valide de l'enum
        "spot_order": 1,
        "highlight": False,
    }

    result = supabase_client.from_("spots").insert(spot_data).execute()

    if not result.data:
        pytest.skip("Impossible de créer le spot de test")

    yield result.data[0]

    # Cleanup
    try:
        supabase_client.from_("spots").delete().eq("id", spot_id).execute()
    except Exception:
        pass


# ── Constantes pour les tests ────────────────────────────────────────────────

# Valeurs valides de l'enum spot_type dans la DB
VALID_SPOT_TYPES = ["attraction", "restaurant", "bar", "hotel", "activite", "transport", "shopping"]

# Valeurs invalides qui doivent être rejetées par la DB
INVALID_SPOT_TYPES = ["other", "monument", "park", "shop", "museum", "café", "invalid", ""]
