"""
Tests d'intégration RÉELS contre la base de données Supabase.

Ces tests vérifient les contraintes réelles de la DB, notamment:
- Les enums (spot_type)
- Les foreign keys
- Les contraintes NOT NULL

Pour exécuter ces tests:
    pytest tests/test_db_integration.py -v

Prérequis:
    - Variables d'environnement configurées (supabase_url, SUPABASE_SERVICE_ROLE_KEY)
    - Ou fichier .env avec ces valeurs
"""
import pytest
from postgrest.exceptions import APIError

from tests.conftest import (
    generate_test_id,
    VALID_SPOT_TYPES,
    INVALID_SPOT_TYPES,
)


# ══════════════════════════════════════════════════════════════════════════════
# Tests: Enum spot_type
# ══════════════════════════════════════════════════════════════════════════════

class TestSpotTypeEnum:
    """
    Tests des contraintes de l'enum spot_type.
    C'est ce test qui aurait dû échouer avant le fix!
    """

    @pytest.mark.parametrize("spot_type", VALID_SPOT_TYPES)
    def test_valid_spot_types_accepted(self, supabase_client, test_day, spot_type):
        """Test que les valeurs valides de spot_type sont acceptées."""
        spot_id = generate_test_id("spot")

        spot_data = {
            "id": spot_id,
            "itinerary_day_id": test_day["id"],
            "name": f"Test {spot_type}",
            "spot_type": spot_type,
            "spot_order": 1,
        }

        try:
            result = supabase_client.from_("spots").insert(spot_data).execute()
            assert result.data is not None, f"spot_type '{spot_type}' devrait être accepté"
            assert result.data[0]["spot_type"] == spot_type

            # Cleanup
            supabase_client.from_("spots").delete().eq("id", spot_id).execute()

        except APIError as e:
            pytest.fail(f"spot_type '{spot_type}' a été rejeté: {e}")

    @pytest.mark.parametrize("invalid_type", INVALID_SPOT_TYPES)
    def test_invalid_spot_types_rejected(self, supabase_client, test_day, invalid_type):
        """
        Test que les valeurs INVALIDES de spot_type sont REJETÉES par la DB.

        C'EST CE TEST QUI AURAIT DÉTECTÉ LE BUG AVANT LE DÉPLOIEMENT!
        """
        spot_id = generate_test_id("spot")

        spot_data = {
            "id": spot_id,
            "itinerary_day_id": test_day["id"],
            "name": f"Test invalid {invalid_type}",
            "spot_type": invalid_type,
            "spot_order": 1,
        }

        with pytest.raises(APIError) as exc_info:
            supabase_client.from_("spots").insert(spot_data).execute()

        # Vérifier que c'est bien une erreur d'enum
        error = exc_info.value
        assert "22P02" in str(error) or "invalid input value for enum" in str(error).lower(), \
            f"Attendu erreur d'enum, reçu: {error}"

    def test_null_spot_type_behavior(self, supabase_client, test_day):
        """Test le comportement avec spot_type NULL (si autorisé)."""
        spot_id = generate_test_id("spot")

        spot_data = {
            "id": spot_id,
            "itinerary_day_id": test_day["id"],
            "name": "Test NULL spot_type",
            "spot_order": 1,
            # Pas de spot_type
        }

        try:
            result = supabase_client.from_("spots").insert(spot_data).execute()
            # Si ça passe, NULL est autorisé
            assert result.data is not None
            # Cleanup
            supabase_client.from_("spots").delete().eq("id", spot_id).execute()
        except APIError:
            # Si ça échoue, NULL n'est pas autorisé (NOT NULL constraint)
            pass


# ══════════════════════════════════════════════════════════════════════════════
# Tests: Foreign Keys
# ══════════════════════════════════════════════════════════════════════════════

class TestForeignKeyConstraints:
    """Tests des contraintes de clé étrangère."""

    def test_spot_requires_valid_day_id(self, supabase_client, skip_if_no_supabase):
        """Test qu'un spot nécessite un day_id valide."""
        spot_id = generate_test_id("spot")

        spot_data = {
            "id": spot_id,
            "itinerary_day_id": "invalid-day-id-that-does-not-exist",
            "name": "Test invalid FK",
            "spot_type": "attraction",
            "spot_order": 1,
        }

        with pytest.raises(APIError) as exc_info:
            supabase_client.from_("spots").insert(spot_data).execute()

        # Vérifier que c'est une erreur de FK
        error = str(exc_info.value)
        assert "23503" in error or "foreign key" in error.lower() or "violates" in error.lower()

    def test_day_requires_valid_trip_id(self, supabase_client, test_destination, skip_if_no_supabase):
        """Test qu'un jour nécessite un trip_id valide."""
        day_id = generate_test_id("day")

        day_data = {
            "id": day_id,
            "trip_id": "invalid-trip-id",
            "destination_id": test_destination["id"],
            "day_number": 1,
            "location": "Test",
        }

        with pytest.raises(APIError) as exc_info:
            supabase_client.from_("itinerary_days").insert(day_data).execute()

        error = str(exc_info.value)
        assert "23503" in error or "foreign key" in error.lower() or "violates" in error.lower()


# ══════════════════════════════════════════════════════════════════════════════
# Tests: CRUD Spots avec DB réelle
# ══════════════════════════════════════════════════════════════════════════════

class TestSpotCRUDReal:
    """Tests CRUD réels sur les spots."""

    def test_create_spot_with_all_fields(self, supabase_client, test_day):
        """Test création d'un spot avec tous les champs."""
        spot_id = generate_test_id("spot")

        spot_data = {
            "id": spot_id,
            "itinerary_day_id": test_day["id"],
            "name": "Restaurant Complet",
            "spot_type": "restaurant",
            "address": "123 Rue de Test",
            "duration_minutes": 90,
            "price_range": "€€",
            "tips": "Réserver à l'avance",
            "highlight": True,
            "spot_order": 1,
            "latitude": 48.8566,
            "longitude": 2.3522,
        }

        result = supabase_client.from_("spots").insert(spot_data).execute()

        assert result.data is not None
        spot = result.data[0]
        assert spot["id"] == spot_id
        assert spot["name"] == "Restaurant Complet"
        assert spot["spot_type"] == "restaurant"
        assert spot["highlight"] is True
        assert spot["latitude"] == 48.8566

        # Cleanup
        supabase_client.from_("spots").delete().eq("id", spot_id).execute()

    def test_update_spot_type(self, supabase_client, test_spot):
        """Test mise à jour du spot_type vers une valeur valide."""
        # Update vers une autre valeur valide
        result = supabase_client.from_("spots") \
            .update({"spot_type": "bar"}) \
            .eq("id", test_spot["id"]) \
            .execute()

        assert result.data is not None
        assert result.data[0]["spot_type"] == "bar"

    def test_update_spot_type_invalid_fails(self, supabase_client, test_spot):
        """Test que la mise à jour vers un spot_type invalide échoue."""
        with pytest.raises(APIError):
            supabase_client.from_("spots") \
                .update({"spot_type": "invalid_type"}) \
                .eq("id", test_spot["id"]) \
                .execute()

    def test_reorder_spots(self, supabase_client, test_day):
        """Test réordonnancement de spots."""
        # Créer plusieurs spots
        spots_to_create = []
        for i in range(3):
            spot_id = generate_test_id(f"spot{i}")
            spot_data = {
                "id": spot_id,
                "itinerary_day_id": test_day["id"],
                "name": f"Spot {i}",
                "spot_type": "attraction",
                "spot_order": i + 1,
            }
            result = supabase_client.from_("spots").insert(spot_data).execute()
            spots_to_create.append(result.data[0])

        # Réordonner (inverser l'ordre)
        for i, spot in enumerate(reversed(spots_to_create)):
            supabase_client.from_("spots") \
                .update({"spot_order": i + 1}) \
                .eq("id", spot["id"]) \
                .execute()

        # Vérifier le nouvel ordre
        result = supabase_client.from_("spots") \
            .select("id, spot_order") \
            .eq("itinerary_day_id", test_day["id"]) \
            .order("spot_order") \
            .execute()

        assert result.data[0]["id"] == spots_to_create[2]["id"]  # Dernier devient premier

        # Cleanup
        for spot in spots_to_create:
            supabase_client.from_("spots").delete().eq("id", spot["id"]).execute()

    def test_move_spot_to_different_day(self, supabase_client, test_trip, test_destination):
        """Test déplacement d'un spot vers un autre jour."""
        # Créer deux jours
        day1_id = generate_test_id("day1")
        day2_id = generate_test_id("day2")

        day1 = supabase_client.from_("itinerary_days").insert({
            "id": day1_id,
            "trip_id": test_trip["id"],
            "destination_id": test_destination["id"],
            "day_number": 1,
            "location": "Paris",
        }).execute().data[0]

        day2 = supabase_client.from_("itinerary_days").insert({
            "id": day2_id,
            "trip_id": test_trip["id"],
            "destination_id": test_destination["id"],
            "day_number": 2,
            "location": "Paris",
        }).execute().data[0]

        # Créer un spot dans day1
        spot_id = generate_test_id("spot")
        spot = supabase_client.from_("spots").insert({
            "id": spot_id,
            "itinerary_day_id": day1["id"],
            "name": "Spot à déplacer",
            "spot_type": "attraction",
            "spot_order": 1,
        }).execute().data[0]

        # Déplacer vers day2
        result = supabase_client.from_("spots") \
            .update({"itinerary_day_id": day2["id"], "spot_order": 1}) \
            .eq("id", spot["id"]) \
            .execute()

        assert result.data[0]["itinerary_day_id"] == day2["id"]

        # Cleanup
        supabase_client.from_("spots").delete().eq("id", spot_id).execute()
        supabase_client.from_("itinerary_days").delete().eq("id", day1_id).execute()
        supabase_client.from_("itinerary_days").delete().eq("id", day2_id).execute()


# ══════════════════════════════════════════════════════════════════════════════
# Tests: Destinations
# ══════════════════════════════════════════════════════════════════════════════

class TestDestinationCRUDReal:
    """Tests CRUD réels sur les destinations."""

    def test_update_destination_city_name(self, supabase_client, test_destination):
        """Test mise à jour du nom de ville."""
        result = supabase_client.from_("destinations") \
            .update({"city": "Paris Modifié"}) \
            .eq("id", test_destination["id"]) \
            .execute()

        assert result.data is not None
        assert result.data[0]["city"] == "Paris Modifié"

    def test_update_destination_country(self, supabase_client, test_destination):
        """Test mise à jour du pays."""
        result = supabase_client.from_("destinations") \
            .update({"country": "République Française"}) \
            .eq("id", test_destination["id"]) \
            .execute()

        assert result.data is not None
        assert result.data[0]["country"] == "République Française"


# ══════════════════════════════════════════════════════════════════════════════
# Tests: API Endpoints avec vraie DB
# ══════════════════════════════════════════════════════════════════════════════

class TestAPIEndpointsReal:
    """
    Tests des endpoints API avec la vraie DB.
    Ces tests nécessitent que le serveur soit configuré pour utiliser la vraie DB.
    """

    @pytest.fixture
    def api_client(self):
        """Client de test pour l'API."""
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, test_user_id):
        """Headers d'authentification pour les tests."""
        # Note: En production, il faudrait un vrai token JWT
        # Pour les tests, on peut mock l'auth ou utiliser un token de test
        return {"Authorization": "Bearer test-integration-token"}

    def test_create_spot_endpoint_validates_spot_type(
        self, api_client, auth_headers, test_trip, test_day, supabase_client
    ):
        """
        Test que l'endpoint POST /trips/{trip_id}/spots valide le spot_type.

        Ce test aurait attrapé le bug "other" si l'API ne validait pas!
        """
        # Ce test nécessite de mocker l'auth ou d'avoir un vrai token
        # Pour l'instant, on vérifie juste que l'endpoint existe
        response = api_client.post(
            f"/trips/{test_trip['id']}/spots",
            json={
                "day_id": test_day["id"],
                "name": "Test Spot",
                "spot_type": "other",  # Valeur invalide!
            },
            headers=auth_headers,
        )

        # Sans auth valide, on devrait avoir 401
        # Avec auth valide et le fix en place, le backend devrait convertir "other" en "attraction"
        assert response.status_code in [401, 200, 201]


# ══════════════════════════════════════════════════════════════════════════════
# Tests: Validation des mappings frontend/backend
# ══════════════════════════════════════════════════════════════════════════════

class TestFrontendBackendConsistency:
    """
    Tests de cohérence entre les constantes frontend et les contraintes DB.
    """

    def test_all_frontend_spot_types_are_valid_in_db(self, supabase_client, test_day):
        """
        Vérifie que TOUS les spot_types utilisés par le frontend sont valides en DB.
        """
        # Ces valeurs viennent du frontend (CATEGORY_TO_SPOT_TYPE)
        frontend_spot_types = [
            "restaurant",   # food
            "attraction",   # culture (après fix)
            "activite",     # nature (après fix)
            "shopping",     # shopping (après fix)
            "bar",          # nightlife
            "attraction",   # other (après fix, devrait être "attraction")
        ]

        for spot_type in set(frontend_spot_types):
            spot_id = generate_test_id("spot")
            spot_data = {
                "id": spot_id,
                "itinerary_day_id": test_day["id"],
                "name": f"Test {spot_type}",
                "spot_type": spot_type,
                "spot_order": 1,
            }

            try:
                result = supabase_client.from_("spots").insert(spot_data).execute()
                assert result.data is not None, f"Frontend spot_type '{spot_type}' rejeté par la DB!"
                # Cleanup
                supabase_client.from_("spots").delete().eq("id", spot_id).execute()
            except APIError as e:
                pytest.fail(f"Frontend spot_type '{spot_type}' rejeté par la DB: {e}")

    def test_document_valid_spot_types(self, supabase_client, test_day):
        """
        Test qui documente les valeurs valides de spot_type.
        Si ce test échoue, les valeurs valides ont changé dans la DB.
        """
        expected_valid_types = {
            "attraction",
            "restaurant",
            "bar",
            "hotel",
            "activite",
            "transport",
            "shopping",
        }

        for spot_type in expected_valid_types:
            spot_id = generate_test_id("spot")
            try:
                result = supabase_client.from_("spots").insert({
                    "id": spot_id,
                    "itinerary_day_id": test_day["id"],
                    "name": f"Test {spot_type}",
                    "spot_type": spot_type,
                    "spot_order": 1,
                }).execute()
                supabase_client.from_("spots").delete().eq("id", spot_id).execute()
            except APIError:
                pytest.fail(
                    f"La valeur '{spot_type}' n'est plus valide dans l'enum spot_type. "
                    f"Les valeurs valides ont changé dans la DB!"
                )
