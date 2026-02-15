# Guide de Migration - De main.py monolithique vers l'architecture refactorisée

## 📊 Vue d'ensemble des changements

| Ancien (main.py) | Nouveau (architecture modulaire) |
|------------------|----------------------------------|
| Tout dans un fichier (~800 lignes) | Code réparti dans 10+ fichiers |
| Variables globales (`ml_state`, `jobs`) | Services avec état encapsulé |
| Fonctions éparpillées | Classes et méthodes organisées |
| Difficile à tester | Chaque composant testable indépendamment |

## 🔄 Correspondance ancien → nouveau code

### 1. Variables globales

**Avant** (`main.py`) :
```python
ml_state: dict = {}
jobs: dict = {}
_executor = ThreadPoolExecutor(max_workers=1)
```

**Après** :
```python
# services/ml_service.py
class MLService:
    def __init__(self):
        self.model = None
        self.processor = None
        # ...

ml_service = MLService()  # Singleton

# services/sse_service.py
class JobManager:
    def __init__(self):
        self.jobs: Dict[str, Dict] = {}

job_manager = JobManager()  # Singleton

# services/job_processor.py
_executor = ThreadPoolExecutor(max_workers=1)
```

### 2. Chargement du modèle

**Avant** :
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    t0 = time.time()
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = Qwen2VLForConditionalGeneration.from_pretrained(...)
    processor = AutoProcessor.from_pretrained(...)
    ml_state["model"] = model
    ml_state["processor"] = processor
    # ...
```

**Après** :
```python
# services/ml_service.py
class MLService:
    def load_model(self, model_id: str, max_pixels: int, fps: float):
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.model = Qwen2VLForConditionalGeneration.from_pretrained(...)
        self.processor = AutoProcessor.from_pretrained(...)

# main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    ml_service.load_model(
        model_id=settings.MODEL_ID,
        max_pixels=settings.MAX_PIXELS,
        fps=settings.FPS,
    )
```

### 3. Inférence ML

**Avant** :
```python
def run_inference(video_path: str):
    model = ml_state["model"]
    processor = ml_state["processor"]
    # ... 100+ lignes de code ...
```

**Après** :
```python
# services/ml_service.py
class MLService:
    def run_inference(self, video_path: str, max_new_tokens: int = 4096):
        # Code d'inférence encapsulé dans la classe
        # ...

# Utilisation
result, duration = ml_service.run_inference(video_path)
```

### 4. Gestion Supabase

**Avant** :
```python
# Multiples fonctions éparpillées
def _sb_headers() -> dict: ...
def _sb_url(table: str) -> str: ...
def _sb_insert(table: str, payload: dict) -> dict: ...
def _sb_update(table: str, payload: dict, eq_col: str, eq_val: str) -> None: ...

async def update_job_in_db(job_id: str, updates: dict): ...
async def create_trip_in_db(trip_data: dict, job_id: str, user_id: Optional[str] = None): ...
```

**Après** :
```python
# services/supabase_service.py
class SupabaseService:
    def __init__(self, url: str, key: str):
        self.url = url
        self.key = key
    
    async def insert(self, table: str, payload: Dict) -> Dict: ...
    async def update(self, table: str, payload: Dict, eq_col: str, eq_val: str): ...
    async def update_job(self, job_id: str, updates: Dict): ...
    async def create_trip(self, trip_data: Dict, job_id: str, user_id: Optional[str]): ...

# Utilisation
supabase_service = SupabaseService(url=..., key=...)
await supabase_service.update_job(job_id, {"status": "done"})
```

### 5. Gestion des jobs SSE

**Avant** :
```python
jobs: dict = {}  # Variable globale

async def send_sse_update(job_id: str, status: str, data: dict = None):
    if job_id not in jobs:
        return
    job = jobs[job_id]
    job["status"] = status
    # ...
```

**Après** :
```python
# services/sse_service.py
class JobManager:
    def __init__(self):
        self.jobs: Dict[str, Dict] = {}
    
    def create_job(self, job_id: str): ...
    def get_job(self, job_id: str): ...
    async def send_sse_update(self, job_id: str, status: str, data: Optional[Dict]): ...

# Utilisation
job_manager = JobManager()
job_manager.create_job(job_id)
await job_manager.send_sse_update(job_id, "downloading", {"progress": 0})
```

### 6. Traitement des jobs

**Avant** :
```python
async def _run_url_job(job_id: str, request: AnalyzeUrlRequest):
    # 150+ lignes mêlant téléchargement, ML, Supabase, SSE...
```

**Après** :
```python
# services/job_processor.py
class JobProcessor:
    def __init__(self, supabase_service: SupabaseService, cookies_file: str, proxy: str):
        self.supabase = supabase_service
        # ...
    
    async def process_url_job(self, job_id: str, request: AnalyzeUrlRequest):
        # Code organisé et clair
        # Utilise ml_service, supabase_service, job_manager
```

### 7. Routes API

**Avant** :
```python
@app.post("/analyze/url", status_code=202)
async def analyze_video_url(request: AnalyzeUrlRequest, background_tasks: BackgroundTasks):
    _check_model_ready()
    job_id = str(uuid.uuid4())
    jobs[job_id] = {...}
    background_tasks.add_task(_run_url_job, job_id, request)
    return {"job_id": job_id}

@app.get("/analyze/stream/{job_id}")
async def stream_job_status(job_id: str):
    # ...

@app.get("/trips/{trip_id}")
async def get_trip(trip_id: str):
    # ...
```

**Après** :
```python
# api/analyze.py
router = APIRouter(prefix="/analyze", tags=["analyze"])

@router.post("/url", status_code=202)
async def analyze_video_url(request: AnalyzeUrlRequest, background_tasks: BackgroundTasks):
    if not ml_service.is_ready():
        raise HTTPException(503, detail="Le modèle n'est pas encore chargé.")
    
    job_id = str(uuid.uuid4())
    job_manager.create_job(job_id)
    background_tasks.add_task(_job_processor.process_url_job, job_id, request)
    return JobResponse(job_id=job_id)

# api/trips.py
router = APIRouter(prefix="/trips", tags=["trips"])

@router.get("/{trip_id}")
async def get_trip(trip_id: str):
    # ...

# main.py
app.include_router(analyze.router)
app.include_router(trips.router)
```

### 8. Schémas Pydantic

**Avant** (dans main.py) :
```python
class AnalyzePathRequest(BaseModel):
    video_path: str

class AnalyzeUrlRequest(BaseModel):
    url: str
    # ...
```

**Après** (dans models/schemas.py) :
```python
# models/schemas.py
class AnalyzePathRequest(BaseModel):
    video_path: str

class AnalyzeUrlRequest(BaseModel):
    url: str
    # ...

class JobResponse(BaseModel):
    job_id: str

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None
```

## 📝 Étapes de migration

### Étape 1 : Copier les fichiers nécessaires
```bash
# Créer le dossier du nouveau projet
mkdir bombo_refactor

# Copier les fichiers que le refactoring ne touche pas
cp config.py bombo_refactor/
cp downloader.py bombo_refactor/
cp requirements.txt bombo_refactor/  # si vous en avez un
```

### Étape 2 : Utiliser les fichiers refactorisés
Les fichiers suivants ont été créés et sont prêts à l'emploi :
- ✅ `main.py`
- ✅ `models/schemas.py`
- ✅ `services/ml_service.py`
- ✅ `services/supabase_service.py`
- ✅ `services/sse_service.py`
- ✅ `services/job_processor.py`
- ✅ `api/analyze.py`
- ✅ `api/trips.py`
- ✅ `utils/prompts.py`

### Étape 3 : Vérifier les dépendances
Votre `requirements.txt` devrait contenir :
```
fastapi
uvicorn[standard]
torch
transformers
qwen-vl-utils
supabase
httpx
yt-dlp
pydantic
python-multipart
json-repair  # optionnel mais recommandé
```

### Étape 4 : Installer et tester
```bash
cd bombo_refactor
pip install -r requirements.txt
python main.py
```

### Étape 5 : Tester les endpoints
```bash
# Health check
curl http://localhost:8000/health

# Analyser une vidéo (remplacer l'URL)
curl -X POST http://localhost:8000/analyze/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/..."}'

# Stream SSE (dans un navigateur ou avec curl)
curl -N http://localhost:8000/analyze/stream/{job_id}
```

## 🎯 Avantages immédiats

### Avant la migration
- ❌ Fichier de 800+ lignes difficile à naviguer
- ❌ Modifications risquées (tout est interconnecté)
- ❌ Tests complexes (tout doit être mocké)
- ❌ Difficile de travailler en équipe (conflits Git)

### Après la migration
- ✅ Fichiers de ~100-200 lignes, faciles à comprendre
- ✅ Modifications isolées (changement dans un service = impact limité)
- ✅ Tests unitaires simples (chaque service est indépendant)
- ✅ Travail en équipe facilité (fichiers séparés = moins de conflits)

## 🧪 Validation de la migration

### Checklist de validation
- [ ] L'application démarre sans erreur
- [ ] Le modèle ML se charge correctement (check `/health`)
- [ ] L'analyse d'une vidéo fonctionne (`POST /analyze/url`)
- [ ] Le stream SSE fonctionne (`GET /analyze/stream/{job_id}`)
- [ ] Les données sont sauvegardées dans Supabase (si configuré)
- [ ] Les routes de récupération fonctionnent (`GET /trips/{id}`)
- [ ] Les logs sont clairs et indiquent le bon module

### Points de vérification
1. **Logging** : Les logs indiquent le module (ex: `bombo.ml_service`, `bombo.api.analyze`)
2. **Performance** : Pas de régression (le refactoring ne change pas la logique)
3. **Fonctionnalités** : Toutes les features de l'ancien code fonctionnent
4. **Erreurs** : Les erreurs sont bien gérées et propagées

## 🐛 Problèmes courants et solutions

### Problème : ImportError
```python
ImportError: cannot import name 'AnalyzeUrlRequest' from 'models.schemas'
```
**Solution** : Vérifier que tous les fichiers `__init__.py` sont présents

### Problème : ml_service.is_ready() retourne False
**Solution** : Vérifier que `lifespan` appelle bien `ml_service.load_model()`

### Problème : job_processor non défini dans analyze.py
**Solution** : Vérifier que `set_job_processor()` est appelé dans `lifespan`

### Problème : Les jobs ne persistent pas entre les requêtes
**Solution** : Normal, `job_manager.jobs` est en mémoire. Pour la persistance, utiliser Supabase

## 📚 Ressources supplémentaires

- **FastAPI Documentation** : https://fastapi.tiangolo.com/
- **Dependency Injection** : https://fastapi.tiangolo.com/tutorial/dependencies/
- **Testing FastAPI** : https://fastapi.tiangolo.com/tutorial/testing/
- **Project Structure** : https://fastapi.tiangolo.com/tutorial/bigger-applications/

## ✨ Prochaines améliorations possibles

1. **Tests unitaires** : Ajouter des tests pour chaque service
2. **Dependency Injection** : Utiliser FastAPI Depends() au lieu de variables globales
3. **Configuration** : Migrer vers Pydantic Settings pour la config
4. **Logging avancé** : Ajouter structured logging (JSON logs)
5. **Monitoring** : Ajouter Prometheus metrics
6. **Documentation** : Enrichir les docstrings et ajouter des exemples
