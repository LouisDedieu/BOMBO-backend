"""
Définition des types de spots valides.

Ce fichier est la SOURCE UNIQUE DE VÉRITÉ pour les valeurs de l'enum spot_type.
Les valeurs ici doivent correspondre EXACTEMENT à l'enum défini dans PostgreSQL.

Enum PostgreSQL: spot_type
Valeurs: attraction | restaurant | bar | hotel | activite | transport | shopping
"""
from enum import Enum
from typing import Set


class SpotType(str, Enum):
    """
    Enum des types de spots valides dans la base de données.

    IMPORTANT: Ces valeurs doivent correspondre EXACTEMENT à l'enum PostgreSQL.
    Ne pas ajouter de nouvelles valeurs sans mettre à jour la DB.
    """
    ATTRACTION = "attraction"
    RESTAURANT = "restaurant"
    BAR = "bar"
    HOTEL = "hotel"
    ACTIVITE = "activite"
    TRANSPORT = "transport"
    SHOPPING = "shopping"


# Set des valeurs valides pour validation rapide
VALID_SPOT_TYPES: Set[str] = {member.value for member in SpotType}

# Valeur par défaut quand le type n'est pas spécifié ou invalide
DEFAULT_SPOT_TYPE: str = SpotType.ATTRACTION.value


def validate_spot_type(spot_type: str | None) -> str:
    """
    Valide et normalise un spot_type.

    Args:
        spot_type: Le type de spot à valider (peut être None)

    Returns:
        Un spot_type valide (DEFAULT_SPOT_TYPE si l'entrée est invalide)

    Examples:
        >>> validate_spot_type("restaurant")
        "restaurant"
        >>> validate_spot_type("other")  # invalide
        "attraction"
        >>> validate_spot_type(None)
        "attraction"
    """
    if spot_type is None:
        return DEFAULT_SPOT_TYPE

    normalized = spot_type.lower().strip()

    if normalized in VALID_SPOT_TYPES:
        return normalized

    return DEFAULT_SPOT_TYPE


def is_valid_spot_type(spot_type: str | None) -> bool:
    """
    Vérifie si un spot_type est valide.

    Args:
        spot_type: Le type de spot à vérifier

    Returns:
        True si valide, False sinon
    """
    if spot_type is None:
        return False
    return spot_type.lower().strip() in VALID_SPOT_TYPES
