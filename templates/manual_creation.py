"""
Templates for manual trip and city creation.
These templates provide pre-filled data for users creating trips/cities manually.
"""

TRIP_TEMPLATE = {
    "trip_title": "Mon nouveau voyage",
    "vibe": "Aventure",
    "destinations": [
        {"city": "Paris", "country": "France", "days_spent": 2}
    ],
    "itinerary": [
        {
            "day": 1,
            "location": "Paris",
            "theme": "Découverte",
            "spots": [
                {"name": "Tour Eiffel", "spot_type": "attraction", "highlight": True},
                {"name": "Restaurant exemple", "spot_type": "restaurant"},
            ]
        },
        {
            "day": 2,
            "location": "Paris",
            "theme": "Culture",
            "spots": [
                {"name": "Musée du Louvre", "spot_type": "attraction"}
            ]
        }
    ]
}

CITY_TEMPLATE = {
    "city_title": "Mon guide de Paris",
    "city_name": "Paris",
    "country": "France",
    "vibe_tags": ["romantic", "cultural"],
    "highlights": [
        {"name": "Restaurant local", "category": "food", "is_must_see": True},
        {"name": "Musée historique", "category": "culture", "is_must_see": True},
        {"name": "Parc central", "category": "nature"},
        {"name": "Quartier shopping", "category": "shopping"},
        {"name": "Bar tendance", "category": "nightlife"},
    ]
}
