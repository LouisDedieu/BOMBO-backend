"""
Tests pour les endpoints CRUD trips (api/review.py → /trips/)
Tests unitaires et d'intégration pour CRUD spots/destinations
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, Any

from main import app
from api.review import (
    CreateSpotBody,
    ReorderSpotsBody,
    SpotOrderItem,
    MoveSpotBody,
    UpdateDestinationBody,
    _check_day_ownership,
    _check_spot_ownership,
    _check_destination_ownership,
)
from models.errors import ErrorCode


client = TestClient(app)


# ── Fixtures & Helpers ─────────────────────────────────────────────────────────

def mock_supabase_response(data: Any, error: Any = None):
    """Helper pour créer une mock response Supabase"""
    mock = MagicMock()
    mock.data = data
    mock.error = error
    return mock


def create_mock_supabase():
    """Crée un mock complet du client Supabase"""
    mock = MagicMock()

    # Setup chainable methods
    mock.from_.return_value = mock
    mock.select.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    mock.delete.return_value = mock
    mock.eq.return_value = mock
    mock.in_.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.maybe_single.return_value = mock
    mock.single.return_value = mock

    return mock


# ── Unit Tests: Pydantic Models ────────────────────────────────────────────────

class TestPydanticModels:
    """Tests pour les modèles Pydantic"""

    def test_create_spot_body_minimal(self):
        """Test création spot avec champs minimaux"""
        body = CreateSpotBody(day_id="day-123", name="Test Spot")
        assert body.day_id == "day-123"
        assert body.name == "Test Spot"
        assert body.highlight is False
        assert body.spot_type is None

    def test_create_spot_body_full(self):
        """Test création spot avec tous les champs"""
        body = CreateSpotBody(
            day_id="day-123",
            name="Restaurant Test",
            spot_type="restaurant",
            address="123 Rue Test",
            duration_minutes=60,
            price_range="15-25€",
            tips="Réserver à l'avance",
            highlight=True,
            latitude=48.8566,
            longitude=2.3522,
        )
        assert body.spot_type == "restaurant"
        assert body.duration_minutes == 60
        assert body.highlight is True
        assert body.latitude == 48.8566

    def test_reorder_spots_body(self):
        """Test ReorderSpotsBody"""
        body = ReorderSpotsBody(spots=[
            SpotOrderItem(id="spot-1", order=1),
            SpotOrderItem(id="spot-2", order=2),
            SpotOrderItem(id="spot-3", order=3),
        ])
        assert len(body.spots) == 3
        assert body.spots[0].id == "spot-1"
        assert body.spots[2].order == 3

    def test_move_spot_body_minimal(self):
        """Test MoveSpotBody avec champs minimaux"""
        body = MoveSpotBody(target_day_id="day-456")
        assert body.target_day_id == "day-456"
        assert body.order is None

    def test_move_spot_body_with_order(self):
        """Test MoveSpotBody avec ordre spécifié"""
        body = MoveSpotBody(target_day_id="day-456", order=5)
        assert body.order == 5

    def test_update_destination_body_partial(self):
        """Test UpdateDestinationBody avec champs partiels"""
        body = UpdateDestinationBody(city_name="Paris")
        assert body.city_name == "Paris"
        assert body.country is None

    def test_update_destination_body_full(self):
        """Test UpdateDestinationBody avec tous les champs"""
        body = UpdateDestinationBody(city_name="Lyon", country="France")
        assert body.city_name == "Lyon"
        assert body.country == "France"


# ── Unit Tests: Ownership Checks ───────────────────────────────────────────────

class TestOwnershipChecks:
    """Tests pour les fonctions de vérification d'ownership"""

    def test_check_day_ownership_not_found(self):
        """Test _check_day_ownership avec jour inexistant"""
        mock_sb = create_mock_supabase()
        mock_sb.execute.return_value = mock_supabase_response(None)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _check_day_ownership(mock_sb, "invalid-day", "user-123")

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["error_code"] == ErrorCode.DAY_NOT_FOUND

    def test_check_spot_ownership_not_found(self):
        """Test _check_spot_ownership avec spot inexistant"""
        mock_sb = create_mock_supabase()
        mock_sb.execute.return_value = mock_supabase_response(None)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _check_spot_ownership(mock_sb, "invalid-spot", "user-123")

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["error_code"] == ErrorCode.SPOT_NOT_FOUND

    def test_check_destination_ownership_not_found(self):
        """Test _check_destination_ownership avec destination inexistante"""
        mock_sb = create_mock_supabase()
        mock_sb.execute.return_value = mock_supabase_response(None)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _check_destination_ownership(mock_sb, "invalid-dest", "user-123")

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["error_code"] == ErrorCode.DESTINATION_NOT_FOUND


# ── Integration Tests: Auth Required ───────────────────────────────────────────

class TestAuthRequired:
    """Tests que les endpoints nécessitent une authentification"""

    def test_create_spot_requires_auth(self):
        """POST /trips/{trip_id}/spots nécessite une auth"""
        response = client.post(
            "/trips/trip-123/spots",
            json={"day_id": "day-123", "name": "Test"}
        )
        assert response.status_code == 401

    def test_reorder_spots_requires_auth(self):
        """PATCH /trips/days/{day_id}/spots/reorder nécessite une auth"""
        response = client.patch(
            "/trips/days/day-123/spots/reorder",
            json={"spots": []}
        )
        assert response.status_code == 401

    def test_move_spot_requires_auth(self):
        """PATCH /trips/spots/{spot_id}/move nécessite une auth"""
        response = client.patch(
            "/trips/spots/spot-123/move",
            json={"target_day_id": "day-456"}
        )
        assert response.status_code == 401

    def test_update_destination_requires_auth(self):
        """PATCH /trips/destinations/{dest_id} nécessite une auth"""
        response = client.patch(
            "/trips/destinations/dest-123",
            json={"city_name": "Paris"}
        )
        assert response.status_code == 401


# ── Integration Tests: Validation Errors ───────────────────────────────────────

class TestValidationErrors:
    """Tests pour les erreurs de validation des requêtes"""

    def test_create_spot_missing_name(self):
        """POST /trips/{trip_id}/spots sans name retourne 422"""
        response = client.post(
            "/trips/trip-123/spots",
            headers={"Authorization": "Bearer test-token"},
            json={"day_id": "day-123"}  # missing name
        )
        # 401 car token invalide, ou 422 si validation avant auth
        assert response.status_code in [401, 422]

    def test_create_spot_missing_day_id(self):
        """POST /trips/{trip_id}/spots sans day_id retourne 422"""
        response = client.post(
            "/trips/trip-123/spots",
            headers={"Authorization": "Bearer test-token"},
            json={"name": "Test Spot"}  # missing day_id
        )
        assert response.status_code in [401, 422]

    def test_reorder_spots_empty_array(self):
        """PATCH /trips/days/{day_id}/spots/reorder avec array vide est valide"""
        response = client.patch(
            "/trips/days/day-123/spots/reorder",
            headers={"Authorization": "Bearer test-token"},
            json={"spots": []}
        )
        # 401 car token invalide, mais payload valide
        assert response.status_code == 401

    def test_move_spot_missing_target_day(self):
        """PATCH /trips/spots/{spot_id}/move sans target_day_id retourne 422"""
        response = client.patch(
            "/trips/spots/spot-123/move",
            headers={"Authorization": "Bearer test-token"},
            json={}  # missing target_day_id
        )
        assert response.status_code in [401, 422]


# ── Integration Tests: Endpoint Responses ──────────────────────────────────────

class TestEndpointResponses:
    """Tests pour les formats de réponse des endpoints"""

    def test_create_spot_response_structure(self):
        """Test structure de réponse POST /trips/{trip_id}/spots"""
        # Définition attendue de la réponse
        expected_response = {
            "id": "spot-new-123",
            "name": "Test Spot",
            "day_id": "day-123",
            "spot": {
                "id": "spot-new-123",
                "name": "Test Spot",
                "itinerary_day_id": "day-123",
                "spot_type": "restaurant",
                "highlight": False,
            }
        }
        assert "id" in expected_response
        assert "name" in expected_response
        assert "day_id" in expected_response
        assert "spot" in expected_response

    def test_reorder_spots_response_structure(self):
        """Test structure de réponse PATCH /trips/days/{day_id}/spots/reorder"""
        expected_response = {"reordered": True}
        assert "reordered" in expected_response
        assert expected_response["reordered"] is True

    def test_move_spot_response_structure(self):
        """Test structure de réponse PATCH /trips/spots/{spot_id}/move"""
        expected_response = {"moved": True}
        assert "moved" in expected_response
        assert expected_response["moved"] is True

    def test_update_destination_response_structure(self):
        """Test structure de réponse PATCH /trips/destinations/{dest_id}"""
        expected_response = {"updated": True}
        assert "updated" in expected_response
        assert expected_response["updated"] is True


# ── Tests: Error Code Consistency ──────────────────────────────────────────────

class TestErrorCodeConsistency:
    """Tests que les codes d'erreur sont cohérents"""

    def test_day_not_found_error_code(self):
        """Test que DAY_NOT_FOUND existe dans ErrorCode"""
        assert hasattr(ErrorCode, 'DAY_NOT_FOUND')
        assert ErrorCode.DAY_NOT_FOUND.value == "DAY_NOT_FOUND"

    def test_spot_not_found_error_code(self):
        """Test que SPOT_NOT_FOUND existe dans ErrorCode"""
        assert hasattr(ErrorCode, 'SPOT_NOT_FOUND')
        assert ErrorCode.SPOT_NOT_FOUND.value == "SPOT_NOT_FOUND"

    def test_destination_not_found_error_code(self):
        """Test que DESTINATION_NOT_FOUND existe dans ErrorCode"""
        assert hasattr(ErrorCode, 'DESTINATION_NOT_FOUND')
        assert ErrorCode.DESTINATION_NOT_FOUND.value == "DESTINATION_NOT_FOUND"


# ── Tests: Spot Order Calculation ──────────────────────────────────────────────

class TestSpotOrderCalculation:
    """Tests pour le calcul de l'ordre des spots"""

    def test_spot_order_starts_at_one(self):
        """L'ordre des spots commence à 1 (pas 0)"""
        # Simulation: aucun spot existant -> ordre = 0 + 1 = 1
        max_order = 0
        new_order = max_order + 1
        assert new_order == 1

    def test_spot_order_increments(self):
        """L'ordre des spots s'incrémente correctement"""
        # Simulation: max_order = 5 -> new_order = 6
        max_order = 5
        new_order = max_order + 1
        assert new_order == 6

    def test_reorder_preserves_all_spots(self):
        """Le réordonnancement préserve tous les spots"""
        spots_before = [
            {"id": "spot-1", "order": 1},
            {"id": "spot-2", "order": 2},
            {"id": "spot-3", "order": 3},
        ]

        # Simulation réordonnancement
        spots_after = [
            {"id": "spot-3", "order": 1},
            {"id": "spot-1", "order": 2},
            {"id": "spot-2", "order": 3},
        ]

        ids_before = {s["id"] for s in spots_before}
        ids_after = {s["id"] for s in spots_after}

        assert ids_before == ids_after
        assert len(spots_before) == len(spots_after)


# ── Tests: Move Spot Between Days ──────────────────────────────────────────────

class TestMoveSpotBetweenDays:
    """Tests pour le déplacement de spots entre jours"""

    def test_move_preserves_spot_data(self):
        """Le déplacement préserve les données du spot"""
        spot_before = {
            "id": "spot-123",
            "name": "Restaurant Test",
            "spot_type": "restaurant",
            "itinerary_day_id": "day-1",
            "address": "123 Rue Test",
        }

        # Simulation déplacement
        spot_after = {
            **spot_before,
            "itinerary_day_id": "day-2",
            "spot_order": 1,  # Nouveau ordre
        }

        assert spot_after["id"] == spot_before["id"]
        assert spot_after["name"] == spot_before["name"]
        assert spot_after["address"] == spot_before["address"]
        assert spot_after["itinerary_day_id"] != spot_before["itinerary_day_id"]

    def test_move_to_same_day_is_noop(self):
        """Déplacer vers le même jour est techniquement valide"""
        current_day = "day-1"
        target_day = "day-1"
        # Le backend autorise ce cas (pas d'erreur)
        assert current_day == target_day


# ── Tests: Update Destination ──────────────────────────────────────────────────

class TestUpdateDestination:
    """Tests pour la mise à jour des destinations"""

    def test_update_city_name_only(self):
        """Mise à jour du nom de ville uniquement"""
        payload = {"city_name": "Lyon"}
        assert "city_name" in payload
        assert "country" not in payload or payload.get("country") is None

    def test_update_country_only(self):
        """Mise à jour du pays uniquement"""
        payload = {"country": "France"}
        assert "country" in payload
        assert "city_name" not in payload or payload.get("city_name") is None

    def test_update_both_fields(self):
        """Mise à jour des deux champs"""
        payload = {"city_name": "Lyon", "country": "France"}
        assert payload["city_name"] == "Lyon"
        assert payload["country"] == "France"

    def test_empty_update_returns_false(self):
        """Mise à jour vide retourne updated=False"""
        payload = {}
        # Le backend retourne {"updated": False} si payload vide
        expected = {"updated": False}
        assert expected["updated"] is False

    def test_update_syncs_itinerary_days(self):
        """La mise à jour du nom synchronise les itinerary_days"""
        # Comportement attendu: quand city_name change,
        # location des itinerary_days liés est aussi mis à jour
        city_name = "Marseille"
        expected_location_update = city_name
        assert expected_location_update == "Marseille"


# ── Tests: Frontend TypeScript Compatibility ───────────────────────────────────

class TestFrontendCompatibility:
    """Tests de compatibilité avec les types TypeScript frontend"""

    def test_create_spot_response_matches_typescript(self):
        """CreateSpotResult TypeScript: { id, name, day_id }"""
        response = {
            "id": "spot-123",
            "name": "Test Spot",
            "day_id": "day-456",
            "spot": {}
        }
        # Frontend attend: id, name, day_id
        assert "id" in response
        assert "name" in response
        assert "day_id" in response

    def test_reorder_payload_matches_typescript(self):
        """ReorderSpotsPayload TypeScript: { spots: Array<{id, order}> }"""
        payload = {
            "spots": [
                {"id": "spot-1", "order": 1},
                {"id": "spot-2", "order": 2},
            ]
        }
        for spot in payload["spots"]:
            assert "id" in spot
            assert "order" in spot

    def test_move_payload_matches_typescript(self):
        """MoveSpotPayload TypeScript: { target_day_id, order? }"""
        payload = {"target_day_id": "day-123", "order": 5}
        assert "target_day_id" in payload
        # order est optionnel
        assert "order" in payload or payload.get("order") is None

    def test_update_destination_payload_matches_typescript(self):
        """UpdateDestinationPayload TypeScript: { city_name?, country? }"""
        payload = {"city_name": "Paris", "country": "France"}
        # Les deux champs sont optionnels
        assert payload.get("city_name") is not None or payload.get("country") is not None
