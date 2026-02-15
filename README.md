# BOMBO - Travel Video Analyzer API (Refactorisé)

## 📁 Structure du projet

```
bombo_refactor/
├── main.py                      # Point d'entrée de l'application
├── config.py                    # Configuration (à créer/copier)
├── downloader.py                # Module de téléchargement vidéo (à copier)
│
├── models/                      # Schémas et modèles de données
│   ├── __init__.py
│   └── schemas.py              # Schémas Pydantic pour les requêtes/réponses
│
├── services/                    # Logique métier
│   ├── __init__.py
│   ├── ml_service.py           # Service de Machine Learning (inférence)
│   ├── supabase_service.py     # Service de gestion de la base de données
│   ├── sse_service.py          # Service de gestion des événements SSE
│   └── job_processor.py        # Service de traitement des jobs d'analyse
│
├── api/                         # Routes et endpoints
│   ├── __init__.py
│   ├── analyze.py              # Routes pour l'analyse de vidéos
│   └── trips.py                # Routes pour la gestion des trips
│
└── utils/                       # Utilitaires
    ├── __init__.py
    └── prompts.py              # Prompts ML et fonctions utilitaires
```

## 🎯 Séparation des responsabilités

### 1. **models/** - Modèles de données
- `schemas.py` : Définit tous les schémas Pydantic pour la validation des requêtes et réponses

### 2. **services/** - Logique métier

#### `ml_service.py`
- Gère le chargement et le déchargement du modèle ML
- Exécute l'inférence sur les vidéos
- Parse et extrait le JSON de la sortie du modèle
- Classe `MLService` avec instance singleton `ml_service`

#### `supabase_service.py`
- Gère toutes les interactions avec Supabase
- Insertion/mise à jour des données
- Normalisation des valeurs enum (saisons)
- Création complète des trips avec toutes leurs relations
- Classe `SupabaseService`

#### `sse_service.py`
- Gère les jobs d'analyse asynchrones
- Gestion des queues SSE pour les mises à jour en temps réel
- Classe `JobManager` avec instance singleton `job_manager`

#### `job_processor.py`
- Orchestre le processus complet d'analyse
- Gère le téléchargement, l'inférence et la sauvegarde
- Coordonne les services ML et Supabase
- Envoie les mises à jour SSE aux clients
- Classe `JobProcessor`

### 3. **api/** - Couche HTTP

#### `analyze.py`
- Route `/analyze/url` : Démarre une analyse
- Route `/analyze/stream/{job_id}` : Stream SSE des mises à jour
- Route `/analyze/status/{job_id}` : Polling de statut (fallback)

#### `trips.py`
- Route `/trips/{trip_id}` : Récupère un voyage
- Route `/trips/user/{user_id}` : Liste des voyages d'un utilisateur

### 4. **utils/** - Utilitaires

#### `prompts.py`
- Contient le prompt pour l'analyse de voyage
- Fonction `get_fallback_result()` pour les résultats par défaut

### 5. **main.py** - Orchestration

- Configuration de l'application FastAPI
- Gestion du cycle de vie (startup/shutdown)
- Initialisation des services
- Configuration des middlewares (CORS)
- Enregistrement des routers
- Route de health check

## 🚀 Avantages de cette architecture

### ✅ Maintenabilité
- Code organisé par responsabilité
- Facile de trouver où modifier une fonctionnalité
- Réduction des conflits lors du travail en équipe

### ✅ Testabilité
- Chaque service peut être testé indépendamment
- Mock facile des dépendances
- Tests unitaires simplifiés

### ✅ Réutilisabilité
- Services réutilisables dans d'autres parties de l'application
- Logique métier séparée de la couche HTTP

### ✅ Évolutivité
- Facile d'ajouter de nouveaux endpoints
- Facile d'ajouter de nouveaux services
- Architecture claire pour l'ajout de fonctionnalités

## 📝 Migration depuis l'ancien code

### Fichiers à copier
```bash
# Copier les fichiers de configuration et dépendances existants
cp config.py bombo_refactor/
cp downloader.py bombo_refactor/
cp requirements.txt bombo_refactor/  # si vous en avez un
```

### Dépendances requises
Les mêmes que dans l'ancien code :
- fastapi
- uvicorn
- torch
- transformers
- qwen-vl-utils
- supabase (optionnel)
- httpx
- yt-dlp
- pydantic
- json-repair (optionnel mais recommandé)

## 🎓 Exemples d'utilisation

### Démarrer l'application
```bash
cd bombo_refactor
python main.py
```

### Ajouter une nouvelle route
1. Créer un nouveau fichier dans `api/` (ex: `api/analytics.py`)
2. Définir le router : `router = APIRouter(prefix="/analytics", tags=["analytics"])`
3. Ajouter les routes
4. Dans `main.py`, importer et enregistrer : `app.include_router(analytics.router)`

### Ajouter un nouveau service
1. Créer un fichier dans `services/` (ex: `services/cache_service.py`)
2. Définir une classe ou des fonctions
3. Importer et utiliser dans les routes ou autres services

### Modifier la logique ML
- Modifier uniquement `services/ml_service.py`
- Aucun impact sur les routes ou la base de données

### Modifier la logique Supabase
- Modifier uniquement `services/supabase_service.py`
- Aucun impact sur le ML ou les routes

## 🔧 Configuration

Les variables d'environnement restent les mêmes que dans l'ancien code :
- `MODEL_ID` : ID du modèle Hugging Face
- `SUPABASE_URL` : URL de votre projet Supabase
- `SUPABASE_SERVICE_KEY` : Clé service_role de Supabase
- `COOKIES_FILE` : Chemin vers le fichier de cookies
- `PROXY_URL` : URL du proxy (optionnel)
- `HOST` et `PORT` : Configuration du serveur

## 📚 Bonnes pratiques

1. **Un fichier = une responsabilité** : Chaque fichier a un objectif clair
2. **Services = logique métier** : Pas de logique dans les routes
3. **Routes = orchestration HTTP** : Validation, appel aux services, réponse
4. **Schémas Pydantic** : Toujours valider les entrées/sorties
5. **Logging** : Utiliser le logger dans chaque module
6. **Gestion d'erreurs** : Lever des HTTPException dans les routes, gérer les exceptions dans les services

## 🐛 Debugging

- Les logs indiquent clairement le module concerné grâce aux noms de logger
- Chaque service peut être testé indépendamment
- Facile de tracer le flux d'une requête : Route → Service → Base de données

## 🎉 Prochaines étapes

1. Copier les fichiers manquants (`config.py`, `downloader.py`)
2. Installer les dépendances
3. Tester l'application
4. Ajouter des tests unitaires pour chaque service
5. Ajouter de la documentation API (Swagger est automatique avec FastAPI)
