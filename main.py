"""
main.py – BOMBO Travel Video Analyzer API (Version améliorée avec SSE)
FastAPI + Qwen2-VL-7B + yt-dlp + Server-Sent Events

NOUVEAUTÉS :
  - Server-Sent Events (SSE) pour remplacer le polling
  - Intégration Supabase pour persistance des jobs
  - Gestion améliorée des erreurs
"""

import torch, time, json, uuid, tempfile, os, logging, asyncio
from typing import Union, Optional
from contextlib import asynccontextmanager
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, field_validator

from transformers import (
    Qwen2VLForConditionalGeneration,
    AutoProcessor,
    StoppingCriteria,
    StoppingCriteriaList,
)
from qwen_vl_utils import process_vision_info

from config import settings
from downloader import (
    download_video,
    UnsupportedURLError,
    PrivateVideoError,
    IPBlockedError,
    DownloadError,
)

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger("bombo.main")


# ── État global ───────────────────────────────────────────────────────────────

ml_state: dict = {}

# Dictionnaire des jobs asynchrones avec queues SSE
# { job_id → { status, result, error, sse_queue: asyncio.Queue } }
jobs: dict = {}

# Exécuteur dédié pour run_inference (bloquant, PyTorch)
_executor = ThreadPoolExecutor(max_workers=1)


# ── Configuration Supabase (optionnelle) ──────────────────────────────────────

SUPABASE_URL = settings.supabase_url or None
SUPABASE_KEY = settings.supabase_service_key or None

# Import conditionnel de Supabase
try:
    from supabase import create_client, Client
    supabase: Optional[Client] = None
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase connecté ✓")
except ImportError:
    supabase = None
    logger.warning("Module supabase-py non installé. Fonctionnement en mode mémoire.")


# ── Cycle de vie du serveur ───────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Chargement du modèle UNE SEULE FOIS au démarrage."""
    t0 = time.time()
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    logger.info("Chargement du modèle sur %s …", device.upper())

    model = Qwen2VLForConditionalGeneration.from_pretrained(
        settings.MODEL_ID,
        torch_dtype=torch.float16,
        device_map={"": device},
        attn_implementation="sdpa",
    )
    processor = AutoProcessor.from_pretrained(settings.MODEL_ID)

    ml_state["model"] = model
    ml_state["processor"] = processor
    ml_state["device"] = device
    logger.info("Modèle prêt en %.2fs ✓", time.time() - t0)

    yield  # ← le serveur tourne ici

    _executor.shutdown(wait=False)
    del ml_state["model"], ml_state["processor"]
    if device == "mps":
        torch.mps.empty_cache()
    logger.info("Modèle déchargé.")


app = FastAPI(title="BOMBO – Travel Video Analyzer API (SSE)", lifespan=lifespan)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev
        "http://localhost:3000",   # CRA / Next dev
        "*",                       # ← restreindre en production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Utilitaire SSE ────────────────────────────────────────────────────────────

async def send_sse_update(job_id: str, status: str, data: dict = None):
    """Envoie une mise à jour via SSE à tous les clients connectés pour ce job."""
    if job_id not in jobs:
        return
    
    job = jobs[job_id]
    job["status"] = status
    
    message = {
        "job_id": job_id,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    if data:
        message.update(data)
    
    # Ajouter à la queue SSE si elle existe
    if "sse_queues" in job:
        for queue in job["sse_queues"]:
            try:
                await queue.put(message)
            except Exception as e:
                logger.error(f"Erreur lors de l'envoi SSE pour job {job_id}: {e}")


# ── Utilitaire Supabase ───────────────────────────────────────────────────────

async def update_job_in_db(job_id: str, updates: dict):
    """Met à jour un job dans Supabase."""
    if not supabase:
        return
    
    try:
        supabase.table("analysis_jobs").update(updates).eq("id", job_id).execute()
        logger.debug(f"Job {job_id} mis à jour dans Supabase")
    except Exception as e:
        logger.error(f"Erreur mise à jour Supabase pour job {job_id}: {e}")


async def create_trip_in_db(trip_data: dict, job_id: str, user_id: Optional[str] = None):
    """Crée un voyage dans Supabase avec toutes ses relations."""
    if not supabase:
        return None
    
    try:
        # 1. Créer le trip principal
        trip_insert = {
            "job_id": job_id,
            "user_id": user_id,
            "trip_title": trip_data.get("trip_title"),
            "vibe": trip_data.get("vibe"),
            "duration_days": trip_data.get("duration_days", 0),
            "best_season": trip_data.get("best_season"),
            "source_url": trip_data.get("source_url"),
            "content_creator_handle": trip_data.get("content_creator", {}).get("handle"),
            "content_creator_links": trip_data.get("content_creator", {}).get("links_mentioned", []),
        }
        
        trip_response = supabase.table("trips").insert(trip_insert).execute()
        trip_id = trip_response.data[0]["id"]
        logger.info(f"Trip créé dans Supabase: {trip_id}")
        
        # 2. Créer les destinations
        destinations = trip_data.get("destinations", [])
        for dest in destinations:
            supabase.table("destinations").insert({
                "trip_id": trip_id,
                "city": dest.get("city"),
                "country": dest.get("country"),
                "days_spent": dest.get("days_spent"),
                "visit_order": dest.get("order", 0),
            }).execute()
        
        # 3. Créer l'itinéraire
        itinerary = trip_data.get("itinerary", [])
        for day_data in itinerary:
            day_insert = {
                "trip_id": trip_id,
                "day_number": day_data.get("day"),
                "location": day_data.get("location"),
                "theme": day_data.get("theme"),
            }
            
            # Accommodation
            acc = day_data.get("accommodation", {})
            if acc:
                day_insert.update({
                    "accommodation_name": acc.get("name"),
                    "accommodation_type": acc.get("type"),
                    "accommodation_price_per_night": acc.get("price_per_night"),
                    "accommodation_tips": acc.get("tips"),
                })
            
            # Meals
            meals = day_data.get("meals", {})
            if meals:
                day_insert.update({
                    "breakfast_spot": meals.get("breakfast"),
                    "lunch_spot": meals.get("lunch"),
                    "dinner_spot": meals.get("dinner"),
                })
            
            day_response = supabase.table("itinerary_days").insert(day_insert).execute()
            day_id = day_response.data[0]["id"]
            
            # 4. Créer les spots
            spots = day_data.get("spots", [])
            for idx, spot in enumerate(spots):
                supabase.table("spots").insert({
                    "itinerary_day_id": day_id,
                    "name": spot.get("name"),
                    "spot_type": spot.get("type"),
                    "address": spot.get("address"),
                    "duration_minutes": spot.get("duration_minutes"),
                    "price_range": spot.get("price_range"),
                    "price_detail": spot.get("price_detail"),
                    "tips": spot.get("tips"),
                    "highlight": spot.get("highlight", False),
                    "spot_order": idx,
                }).execute()
        
        # 5. Créer la logistique
        logistics = trip_data.get("logistics", [])
        for idx, log in enumerate(logistics):
            supabase.table("logistics").insert({
                "trip_id": trip_id,
                "from_location": log.get("from"),
                "to_location": log.get("to"),
                "transport_mode": log.get("mode"),
                "duration": log.get("duration"),
                "cost": log.get("cost"),
                "tips": log.get("tips"),
                "travel_order": idx,
            }).execute()
        
        # 6. Créer le budget
        budget = trip_data.get("budget", {})
        if budget:
            per_day = budget.get("per_day", {})
            breakdown = budget.get("breakdown", {})
            
            supabase.table("budgets").insert({
                "trip_id": trip_id,
                "total_estimated": budget.get("total_estimated"),
                "currency": budget.get("currency", "EUR"),
                "per_day_min": per_day.get("min"),
                "per_day_max": per_day.get("max"),
                "accommodation_cost": breakdown.get("accommodation"),
                "food_cost": breakdown.get("food"),
                "transport_cost": breakdown.get("transport"),
                "activities_cost": breakdown.get("activities"),
                "money_saving_tips": budget.get("money_saving_tips", []),
            }).execute()
        
        # 7. Créer les infos pratiques
        practical = trip_data.get("practical_info", {})
        if practical:
            supabase.table("practical_info").insert({
                "trip_id": trip_id,
                "visa_required": practical.get("visa_required"),
                "local_currency": practical.get("local_currency"),
                "language": practical.get("language"),
                "best_apps": practical.get("best_apps", []),
                "what_to_pack": practical.get("what_to_pack", []),
                "safety_tips": practical.get("safety_tips", []),
                "things_to_avoid": practical.get("avoid", []),
            }).execute()
        
        logger.info(f"Trip {trip_id} complètement créé dans Supabase")
        return trip_id
        
    except Exception as e:
        logger.error(f"Erreur création trip dans Supabase: {e}")
        return None


# ── Schémas Pydantic (identiques à l'original) ────────────────────────────────

class AnalyzePathRequest(BaseModel):
    video_path: str

class AnalyzeUrlRequest(BaseModel):
    url: str
    cookies_file: str | None = None
    proxy: str | None = None
    user_id: str | None = None  # Nouveau : pour lier à un utilisateur

    @field_validator("url")
    @classmethod
    def url_must_be_https(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("http"):
            raise ValueError("L'URL doit commencer par http:// ou https://")
        return v


# ── Prompt et inférence (identiques à l'original) ─────────────────────────────

TRAVEL_PROMPT = """[... prompt identique à l'original ...]"""

# Fonction run_inference identique à l'original (pas de changement)
def run_inference(video_path: str):
    """Fonction synchrone d'inférence — bloquante, appelée dans ThreadPoolExecutor."""
    t0 = time.time()
    model = ml_state["model"]
    processor = ml_state["processor"]
    device = ml_state["device"]

    messages = [{"role": "user", "content": [
        {
            "type": "video",
            "video": video_path,
            "max_pixels": settings.MAX_PIXELS,
            "fps": settings.FPS,
        },
        {
            "type": "text",
            "text": TRAVEL_PROMPT,
        }
    ]}]

    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text], images=image_inputs, videos=video_inputs,
        padding=True, return_tensors="pt",
    ).to(device)

    stopping = StoppingCriteriaList([JSONClosedStopping(processor)])

    t0 = time.time()
    with torch.inference_mode():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=settings.MAX_NEW_TOKENS,
            stopping_criteria=stopping,
        )
    duration = round(time.time() - t0, 2)
    tokens_generated = generated_ids.shape[-1] - inputs.input_ids.shape[-1]
    logger.info(
        "Generation terminee : %d tokens en %.2fs (%.1f tok/s)",
        tokens_generated, duration, tokens_generated / max(duration, 0.01),
    )

    trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated_ids)]
    raw_text = processor.batch_decode(
        trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )[0]

    logger.debug("Sortie brute du modele (%d cars) : %s", len(raw_text), raw_text[:300])

    start_idx = raw_text.find('{')
    end_idx   = raw_text.rfind('}') + 1
    if start_idx == -1 or end_idx == 0:
        logger.error("Aucun bloc JSON detecte dans la sortie du modele.")
        return _fallback_error(), duration

    json_str = raw_text[start_idx:end_idx]
    json_str = json_str.replace("\\'", "'")
    json_str = json_str.replace("\\n", " ")

    try:
        return json.loads(json_str), duration
    except json.JSONDecodeError as e:
        logger.warning("json.loads echoue (%s) -- tentative json-repair...", e)

    try:
        from json_repair import repair_json
        repaired = repair_json(json_str, return_objects=True)
        if isinstance(repaired, dict) and "trip_title" in repaired:
            logger.info("JSON repare avec succes via json-repair.")
            return repaired, duration
        logger.warning("json-repair n'a pas produit un dict valide : %s", type(repaired))
    except ImportError:
        logger.warning("json-repair non installe. Installez : pip install json-repair")
    except Exception as e:
        logger.warning("json-repair a echoue : %s", e)

    logger.error(
        "Toutes les tentatives de parsing ont echoue.\nSortie brute (%d cars) :\n%s",
        len(raw_text), raw_text[:800],
    )

    return result_dict, duration


def _check_model_ready():
    """Vérifie que le modèle est chargé."""
    if "model" not in ml_state:
        raise HTTPException(503, detail="Le modèle n'est pas encore chargé.")


# ── Job asynchrone avec SSE ───────────────────────────────────────────────────

async def _run_url_job(job_id: str, request: AnalyzeUrlRequest):
    """
    Exécute l'analyse en arrière-plan et envoie des mises à jour SSE.
    """
    try:
        # Créer le job dans Supabase
        if supabase:
            await update_job_in_db(job_id, {
                "id": job_id,
                "user_id": request.user_id,
                "source_url": request.url,
                "status": "pending",
            })
        
        # ── Étape 1 : Téléchargement ─────────────────────────────────────────
        await send_sse_update(job_id, "downloading", {"progress": 0})
        if supabase:
            await update_job_in_db(job_id, {"status": "downloading"})
        
        logger.info("[job %s] Téléchargement de %s", job_id, request.url)
        
        try:
            output_path = await asyncio.to_thread(
                download_video,
                request.url,
                cookies_file=request.cookies_file or settings.COOKIES_FILE,
                proxy=request.proxy or settings.PROXY_URL,
                timeout=settings.DOWNLOAD_TIMEOUT,
            )
        except UnsupportedURLError:
            error_msg = "URL non supportée (accepte TikTok, Instagram Reels)."
            jobs[job_id].update(status="error", error=error_msg)
            await send_sse_update(job_id, "error", {"error": error_msg})
            if supabase:
                await update_job_in_db(job_id, {"status": "error", "error_message": error_msg})
            return
        except (PrivateVideoError, IPBlockedError, DownloadError) as exc:
            error_msg = str(exc)
            jobs[job_id].update(status="error", error=error_msg)
            await send_sse_update(job_id, "error", {"error": error_msg})
            if supabase:
                await update_job_in_db(job_id, {"status": "error", "error_message": error_msg})
            return

        logger.info("[job %s] Vidéo téléchargée : %s", job_id, output_path)
        await send_sse_update(job_id, "downloading", {"progress": 50})

        # ── Étape 2 : Analyse ────────────────────────────────────────────────
        await send_sse_update(job_id, "analyzing", {"progress": 50})
        if supabase:
            await update_job_in_db(job_id, {"status": "analyzing"})
        
        logger.info("[job %s] Début de l'inférence", job_id)
        
        try:
            loop = asyncio.get_event_loop()
            result, duration = await loop.run_in_executor(
                _executor, run_inference, output_path
            )
            
            # Envoyer progression pendant l'analyse
            await send_sse_update(job_id, "analyzing", {"progress": 75})
            
        except Exception as exc:
            logger.exception("[job %s] Erreur lors de l'inférence", job_id)
            error_msg = f"Erreur d'inférence : {exc}"
            jobs[job_id].update(status="error", error=error_msg)
            await send_sse_update(job_id, "error", {"error": error_msg})
            if supabase:
                await update_job_in_db(job_id, {"status": "error", "error_message": error_msg})
            return

        # ── Étape 3 : Sauvegarde dans Supabase ──────────────────────────────
        trip_id = None
        if supabase:
            await send_sse_update(job_id, "analyzing", {"progress": 90, "message": "Sauvegarde..."})
            trip_id = await create_trip_in_db(result, job_id, request.user_id)

        # ── Terminé ──────────────────────────────────────────────────────────
        itinerary = {
            "job_id": job_id,
            "trip_id": trip_id,
            "duration_seconds": duration,
            "raw_json": result,
            "source_url": request.url,
        }
        
        jobs[job_id].update(status="done", result=itinerary)
        await send_sse_update(job_id, "done", {"result": itinerary, "progress": 100})
        
        if supabase:
            await update_job_in_db(job_id, {
                "status": "done",
                "completed_at": datetime.utcnow().isoformat(),
                "duration_seconds": duration,
            })
        
        logger.info("[job %s] Terminé en %.2fs", job_id, duration)
        
    except Exception as exc:
        logger.exception("[job %s] Erreur inattendue", job_id)
        error_msg = f"Erreur inattendue : {exc}"
        jobs[job_id].update(status="error", error=error_msg)
        await send_sse_update(job_id, "error", {"error": error_msg})
        if supabase:
            await update_job_in_db(job_id, {"status": "error", "error_message": error_msg})


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {
        "status": "ok" if "model" in ml_state else "loading",
        "model": settings.MODEL_ID,
        "device": ml_state.get("device", "unknown"),
        "model_loaded": "model" in ml_state,
        "supabase_connected": supabase is not None,
    }


@app.post("/analyze/url", status_code=202)
async def analyze_video_url(
    request: AnalyzeUrlRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Démarre l'analyse en arrière-plan et retourne immédiatement un job_id.
    Le client doit ensuite se connecter à /analyze/stream/{job_id} pour
    recevoir les mises à jour en temps réel via Server-Sent Events.
    """
    _check_model_ready()

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "pending",
        "result": None,
        "error": None,
        "sse_queues": []  # Liste des queues SSE connectées
    }
    
    background_tasks.add_task(_run_url_job, job_id, request)

    logger.info("Job %s créé pour %s", job_id, request.url)
    return {"job_id": job_id}


@app.get("/analyze/stream/{job_id}")
async def stream_job_status(job_id: str):
    """
    Stream SSE des mises à jour du job d'analyse.
    Le client reçoit automatiquement tous les changements de statut.
    
    Format des messages SSE :
    {
        "job_id": "uuid",
        "status": "pending|downloading|analyzing|done|error",
        "progress": 0-100,
        "timestamp": "ISO-8601",
        "result": {...},  // uniquement quand status=done
        "error": "...",   // uniquement quand status=error
    }
    """
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, detail=f"Job introuvable : {job_id}")
    
    # Créer une queue pour ce client SSE
    queue = asyncio.Queue()
    job["sse_queues"].append(queue)
    
    async def event_generator():
        try:
            # Envoyer l'état actuel immédiatement
            current_status = {
                "job_id": job_id,
                "status": job["status"],
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            if job["status"] == "done" and job.get("result"):
                current_status["result"] = job["result"]
            elif job["status"] == "error" and job.get("error"):
                current_status["error"] = job["error"]
            
            yield f"data: {json.dumps(current_status)}\n\n"
            
            # Si déjà terminé, fermer la connexion
            if job["status"] in ["done", "error"]:
                return
            
            # Sinon, attendre les mises à jour
            while True:
                message = await queue.get()
                yield f"data: {json.dumps(message)}\n\n"
                
                # Fermer après done ou error
                if message.get("status") in ["done", "error"]:
                    break
                    
        except asyncio.CancelledError:
            logger.info(f"Client SSE déconnecté pour job {job_id}")
        finally:
            # Retirer la queue de la liste
            if queue in job["sse_queues"]:
                job["sse_queues"].remove(queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Pour nginx
        }
    )


@app.get("/analyze/status/{job_id}")
async def get_job_status(job_id: str):
    """
    Route de fallback pour récupérer le statut d'un job (polling classique).
    Préférer /analyze/stream/{job_id} pour une expérience temps réel.
    """
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, detail=f"Job introuvable : {job_id}")

    return JSONResponse(content={
        "job_id": job_id,
        "status": job["status"],
        "result": job.get("result"),
        "error": job.get("error"),
    })


# ── Routes supplémentaires ────────────────────────────────────────────────────

@app.get("/trips/{trip_id}")
async def get_trip(trip_id: str):
    """Récupère un voyage complet depuis Supabase."""
    if not supabase:
        raise HTTPException(503, detail="Supabase non configuré")
    
    try:
        response = supabase.from_("trip_details").select("*").eq("trip_id", trip_id).execute()
        if not response.data:
            raise HTTPException(404, detail="Voyage introuvable")
        return response.data[0]
    except Exception as e:
        logger.error(f"Erreur récupération trip {trip_id}: {e}")
        raise HTTPException(500, detail=str(e))


@app.get("/user/{user_id}/trips")
async def get_user_trips(user_id: str):
    """Récupère tous les voyages d'un utilisateur."""
    if not supabase:
        raise HTTPException(503, detail="Supabase non configuré")
    
    try:
        response = supabase.from_("trip_details").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        logger.error(f"Erreur récupération trips user {user_id}: {e}")
        raise HTTPException(500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
