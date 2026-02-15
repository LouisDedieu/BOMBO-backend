# Architecture BOMBO - Diagramme visuel

## 📐 Vue d'ensemble de l'architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENT (Frontend)                           │
│                    HTTP/REST API + SSE Stream                        │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           main.py (FastAPI)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  ┌─────────────┐ │
│  │  Lifespan   │  │    CORS     │  │  Routers   │  │   Health    │ │
│  │  Manager    │  │ Middleware  │  │  Registry  │  │   Check     │ │
│  └─────────────┘  └─────────────┘  └────────────┘  └─────────────┘ │
└────────────────────────────┬───────────────┬────────────────────────┘
                             │               │
              ┌──────────────┘               └──────────────┐
              │                                             │
              ▼                                             ▼
┌──────────────────────────┐                  ┌──────────────────────────┐
│   api/analyze.py         │                  │   api/trips.py           │
│  ┌────────────────────┐  │                  │  ┌────────────────────┐  │
│  │ POST /analyze/url  │  │                  │  │ GET /trips/{id}    │  │
│  │ GET /stream/{id}   │  │                  │  │ GET /user/{id}/    │  │
│  │ GET /status/{id}   │  │                  │  │     trips          │  │
│  └────────────────────┘  │                  │  └────────────────────┘  │
└────────────┬─────────────┘                  └────────────┬─────────────┘
             │                                             │
             │                                             │
             ▼                                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        SERVICES LAYER                                │
│                                                                       │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │  JobProcessor    │  │  JobManager      │  │  MLService       │   │
│  │  (Orchestration) │  │  (SSE Events)    │  │  (Inference)     │   │
│  │                  │  │                  │  │                  │   │
│  │ • Download       │  │ • Create job     │  │ • Load model     │   │
│  │ • Analyze        │  │ • Update status  │  │ • Run inference  │   │
│  │ • Save           │  │ • Send SSE       │  │ • Parse JSON     │   │
│  │ • Error handling │  │ • Manage queues  │  │ • Extract result │   │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘   │
│           │                     │                     │             │
│           └─────────────────────┼─────────────────────┘             │
│                                 │                                   │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │              SupabaseService (Database)                        │ │
│  │                                                                │ │
│  │  • insert()      • update_job()      • normalize_season()     │ │
│  │  • update()      • create_trip()     • get_trip()             │ │
│  │  • get_user_trips()                  • discover_enums()       │ │
│  └────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────┬───────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   External Services   │
                    │                       │
                    │  • Supabase (DB)      │
                    │  • yt-dlp (Download)  │
                    │  • Torch (ML)         │
                    └───────────────────────┘
```

## 🔄 Flux de données pour l'analyse d'une vidéo

```
1. CLIENT
   │
   │  POST /analyze/url {"url": "..."}
   │
   ▼
2. api/analyze.py
   │  • Valide la requête (Pydantic)
   │  • Crée un job_id
   │  • Enregistre le job dans JobManager
   │  • Lance le traitement en arrière-plan
   │
   │  Retourne {"job_id": "abc-123"}
   ▼
3. JobProcessor.process_url_job()
   │
   │  ┌─ ÉTAPE 1: Téléchargement ─────────────────┐
   │  │                                            │
   │  │  • Envoie SSE: "downloading" (0%)          │
   │  │  • Appelle download_video() (yt-dlp)       │
   │  │  • Gère les erreurs spécifiques            │
   │  │  • Envoie SSE: "downloading" (50%)         │
   │  │                                            │
   │  └────────────────────────────────────────────┘
   │
   │  ┌─ ÉTAPE 2: Analyse ML ──────────────────────┐
   │  │                                            │
   │  │  • Envoie SSE: "analyzing" (50%)           │
   │  │  • Appelle MLService.run_inference()       │
   │  │    ├─ Charge la vidéo                      │
   │  │    ├─ Prépare le prompt                    │
   │  │    ├─ Exécute le modèle (Qwen2-VL)         │
   │  │    ├─ Parse le JSON                        │
   │  │    └─ Retourne le résultat                 │
   │  │  • Envoie SSE: "analyzing" (75%)           │
   │  │                                            │
   │  └────────────────────────────────────────────┘
   │
   │  ┌─ ÉTAPE 3: Sauvegarde DB ───────────────────┐
   │  │                                            │
   │  │  • Envoie SSE: "analyzing" (90%)           │
   │  │  • Appelle SupabaseService.create_trip()   │
   │  │    ├─ Crée le trip principal               │
   │  │    ├─ Crée les destinations                │
   │  │    ├─ Crée l'itinéraire                    │
   │  │    ├─ Crée les spots                       │
   │  │    ├─ Crée la logistique                   │
   │  │    ├─ Crée le budget                       │
   │  │    └─ Crée les infos pratiques             │
   │  │  • Retourne trip_id                        │
   │  │                                            │
   │  └────────────────────────────────────────────┘
   │
   │  • Envoie SSE: "done" (100%) avec résultat
   │
   ▼
4. CLIENT reçoit les mises à jour en temps réel via SSE
   │
   │  GET /analyze/stream/{job_id}
   │
   │  Reçoit :
   │  ✓ data: {"status": "downloading", "progress": 0}
   │  ✓ data: {"status": "downloading", "progress": 50}
   │  ✓ data: {"status": "analyzing", "progress": 50}
   │  ✓ data: {"status": "analyzing", "progress": 75}
   │  ✓ data: {"status": "analyzing", "progress": 90}
   │  ✓ data: {"status": "done", "result": {...}, "progress": 100}
   │
   ▼
5. CLIENT affiche le résultat
```

## 🔀 Flux SSE (Server-Sent Events)

```
CLIENT                    JobManager              JobProcessor
  │                           │                         │
  │  GET /stream/{job_id}     │                         │
  ├──────────────────────────>│                         │
  │                           │                         │
  │  ┌────── SSE Stream ──────┤                         │
  │  │                        │                         │
  │  │  Crée asyncio.Queue    │                         │
  │  │  Ajoute à job.queues   │                         │
  │  │                        │                         │
  │  │  Envoie état actuel    │                         │
  │<─┤                        │                         │
  │  │                        │                         │
  │  │                        │  send_sse_update()      │
  │  │                        │<────────────────────────┤
  │  │                        │                         │
  │  │  Met le message        │                         │
  │  │  dans la queue         │                         │
  │  │                        │                         │
  │<─┤  Envoie au client      │                         │
  │  │  data: {...}           │                         │
  │  │                        │                         │
  │  │  ... heartbeat ...     │                         │
  │<─┤  : heartbeat           │                         │
  │  │                        │                         │
  │  │                        │  send_sse_update()      │
  │  │                        │<────────────────────────┤
  │<─┤  data: {...}           │                         │
  │  │                        │                         │
  │  │  Status = "done"       │                         │
  │  │  Ferme la connexion    │                         │
  │  └────────────────────────┤                         │
  │                           │                         │
```

## 🏗️ Diagramme de classes (simplifié)

```
┌────────────────────────┐
│      MLService         │
├────────────────────────┤
│ - model                │
│ - processor            │
│ - device               │
├────────────────────────┤
│ + load_model()         │
│ + run_inference()      │
│ + is_ready()           │
│ + unload_model()       │
└────────────────────────┘

┌────────────────────────┐
│    JobManager          │
├────────────────────────┤
│ - jobs: Dict           │
├────────────────────────┤
│ + create_job()         │
│ + get_job()            │
│ + update_job_status()  │
│ + send_sse_update()    │
│ + add_sse_queue()      │
│ + remove_sse_queue()   │
└────────────────────────┘

┌────────────────────────┐
│  SupabaseService       │
├────────────────────────┤
│ - url: str             │
│ - key: str             │
│ - season_enum_values   │
├────────────────────────┤
│ + insert()             │
│ + update()             │
│ + create_trip()        │
│ + update_job()         │
│ + get_trip()           │
│ + get_user_trips()     │
│ + normalize_season()   │
└────────────────────────┘

┌────────────────────────┐
│   JobProcessor         │
├────────────────────────┤
│ - supabase_service     │
│ - default_cookies      │
│ - default_proxy        │
├────────────────────────┤
│ + process_url_job()    │
│ - _handle_error()      │
│ + shutdown()           │
└────────────────────────┘
          │
          │ uses
          ▼
    ┌───────────┬───────────┬───────────┐
    │           │           │           │
    ▼           ▼           ▼           ▼
MLService  JobManager  Supabase   download_video()
```

## 📊 Dépendances entre modules

```
main.py
  │
  ├─► api/analyze.py
  │     └─► services/job_processor.py
  │           ├─► services/ml_service.py
  │           ├─► services/supabase_service.py
  │           ├─► services/sse_service.py
  │           └─► downloader.py
  │
  ├─► api/trips.py
  │     └─► services/supabase_service.py
  │
  ├─► models/schemas.py
  │
  └─► utils/prompts.py

Légende:
  ─►  : importe/utilise
  └─► : dépendance directe
```

## 🎯 Points clés de l'architecture

### ✅ Séparation des responsabilités
- **API Layer** (`api/`) : Validation HTTP, routing
- **Service Layer** (`services/`) : Logique métier
- **Models** (`models/`) : Structures de données
- **Utils** (`utils/`) : Fonctions utilitaires

### ✅ Inversion de dépendance
- Les services ne connaissent pas les routes
- Les routes dépendent des services (pas l'inverse)
- Configuration via injection au démarrage

### ✅ Single Responsibility
- Chaque classe a UNE responsabilité claire
- MLService = ML uniquement
- SupabaseService = DB uniquement
- JobProcessor = Orchestration uniquement

### ✅ Testabilité
- Services indépendants
- Mock facile
- Pas de variables globales (sauf singletons contrôlés)

### ✅ Extensibilité
- Facile d'ajouter de nouveaux services
- Facile d'ajouter de nouvelles routes
- Pattern clair à suivre
