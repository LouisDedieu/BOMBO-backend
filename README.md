# 🗺️ Travel Video Analyzer — Backend FastAPI

Transforme une vidéo TikTok/Reel en itinéraire JSON structuré via l'IA multimodale Qwen2-VL.

---

## 🏗️ Architecture

```
travel-api/
├── main.py           # Serveur FastAPI + logique d'inférence
├── config.py         # Paramètres centralisés (modèle, FPS, tokens...)
├── requirements.txt  # Dépendances Python
└── README.md         # Ce fichier
```

**Différence clé avec le script de lab :**
| Script de lab | API FastAPI |
|---|---|
| Modèle chargé à chaque exécution | Modèle chargé **une seule fois** au démarrage |
| ~38s total (8s chargement + 30s inférence) | ~30s total (0s chargement + 30s inférence) |
| Un seul fichier, pas de concurrence | Prêt pour requêtes multiples |

---

## ⚡ Installation & Démarrage

```bash
# 1. Créer l'environnement virtuel
python -m venv venv
source venv/bin/activate

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Lancer le serveur
uvicorn main:app --host 0.0.0.0 --port 8000

# En mode dev (rechargement auto sur modif du code — attention: recharge le modèle !)
# uvicorn main:app --reload
```

Tu verras dans le terminal :
```
🚀 Démarrage du serveur — chargement du modèle Qwen/Qwen2-VL-7B-Instruct...
   Device détecté : MPS
✅ Modèle prêt en 7.3s — l'API est opérationnelle !
```

---

## 🔌 Endpoints

### `GET /health`
Vérifie que le serveur et le modèle sont prêts.
```json
{
  "status": "ok",
  "model": "Qwen/Qwen2-VL-7B-Instruct",
  "device": "mps",
  "model_loaded": true
}
```

### `POST /analyze/upload`
Envoie une vidéo directement (multipart form-data).

```bash
curl -X POST http://localhost:8000/analyze/upload \
  -F "file=@ma_video.mp4"
```

### `POST /analyze/path`
Analyse via un chemin local (préparation pour yt-dlp à l'Étape 2).

```bash
curl -X POST http://localhost:8000/analyze/path \
  -H "Content-Type: application/json" \
  -d '{"video_path": "/chemin/vers/video.mp4"}'
```

**Réponse (les deux endpoints) :**
```json
{
  "job_id": "a1b2c3d4-...",
  "duration_seconds": 29.4,
  "raw_json": {
    "location": "Lisbonne, Portugal",
    "spots": [
      {
        "name": "Pastéis de Belém",
        "type": "restaurant",
        "address": "R. de Belém 84-92",
        "price_range": "€",
        "tips": "Arriver avant 9h pour éviter la queue"
      }
    ],
    "vibe": "Ville historique et solaire, idéale pour les foodies",
    "budget": { "min_per_day": 60, "max_per_day": 120, "currency": "EUR" },
    "best_season": "printemps",
    "tips": ["Prendre le tram 28", "Éviter août (trop touristique)"]
  }
}
```

---

## 🎛️ Tuning des performances (`config.py`)

| Paramètre | Valeur actuelle | Si tu veux + de vitesse | Si tu veux + de précision |
|---|---|---|---|
| `MODEL_ID` | `Qwen2-VL-7B` | Passe en `2B` | Reste en `7B` |
| `FPS` | `0.2` (1/5s) | `0.1` (1/10s) | `0.5` (1/2s) |
| `MAX_PIXELS` | `360×420` | Réduire | `640×480` |
| `MAX_NEW_TOKENS` | `512` | `256` | `1024` |

---

## 🗺️ Roadmap

- [x] **Étape 1** — Backend FastAPI avec modèle persistant ✅
- [ ] **Étape 2** — Intégration `yt-dlp` pour analyser depuis une URL TikTok
- [ ] **Étape 3** — Application mobile (Flutter/React Native) avec Share Extension
- [ ] **Étape 4** — Persistance des itinéraires (Supabase/Firebase)

> 📖 La documentation interactive Swagger est disponible sur `http://localhost:8000/docs`
