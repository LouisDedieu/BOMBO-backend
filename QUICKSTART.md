# 🚀 Démarrage rapide - BOMBO Refactorisé

## ⚡ Installation en 5 minutes

### 1. Prérequis
- Python 3.9 ou supérieur
- GPU recommandé (mais fonctionne aussi sur CPU/MPS)
- ~10GB d'espace disque pour le modèle ML

### 2. Copier les fichiers existants

```bash
# Depuis votre ancien projet, copiez ces fichiers :
cp /path/to/old/config.py bombo_refactor/
cp /path/to/old/downloader.py bombo_refactor/

# Si vous n'avez pas ces fichiers, utilisez les exemples fournis
cp config.example.py config.py
# (et modifiez config.py selon vos besoins)
```

### 3. Installer les dépendances

```bash
cd bombo_refactor
python -m venv venv
source venv/bin/activate  # Sur Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configuration

Créez un fichier `.env` à la racine du projet :

```bash
# .env
MODEL_ID=Qwen/Qwen2-VL-7B-Instruct
HOST=0.0.0.0
PORT=8000

# Optionnel - Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJhbG...

# Optionnel - Download
COOKIES_FILE=/path/to/cookies.txt
PROXY_URL=http://proxy:8080
```

### 5. Lancer l'application

```bash
python main.py
```

Ou avec uvicorn directement :

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Tester

```bash
# Health check
curl http://localhost:8000/health

# Devrait retourner :
{
  "status": "ok",
  "model": "Qwen/Qwen2-VL-7B-Instruct",
  "device": "mps",
  "model_loaded": true,
  "supabase_connected": true
}
```

## 🎯 Premier test d'analyse

### Via curl

```bash
# 1. Démarrer une analyse
curl -X POST http://localhost:8000/analyze/url \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.tiktok.com/@user/video/123",
    "user_id": "test-user"
  }'

# Réponse :
# {"job_id": "abc-123-def-456"}

# 2. Stream SSE des mises à jour
curl -N http://localhost:8000/analyze/stream/abc-123-def-456

# Vous verrez en temps réel :
# data: {"job_id":"abc-123","status":"downloading","progress":0}
# data: {"job_id":"abc-123","status":"downloading","progress":50}
# data: {"job_id":"abc-123","status":"analyzing","progress":50}
# ...
# data: {"job_id":"abc-123","status":"done","result":{...}}
```

### Via Python

```python
import requests
import sseclient

# 1. Démarrer l'analyse
response = requests.post(
    "http://localhost:8000/analyze/url",
    json={"url": "https://www.tiktok.com/@user/video/123"}
)
job_id = response.json()["job_id"]

# 2. Écouter les mises à jour SSE
response = requests.get(
    f"http://localhost:8000/analyze/stream/{job_id}",
    stream=True
)

client = sseclient.SSEClient(response)
for event in client.events():
    print(f"Update: {event.data}")
```

### Via JavaScript (Frontend)

```javascript
// 1. Démarrer l'analyse
const response = await fetch('http://localhost:8000/analyze/url', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    url: 'https://www.tiktok.com/@user/video/123'
  })
});
const { job_id } = await response.json();

// 2. Écouter les mises à jour SSE
const eventSource = new EventSource(
  `http://localhost:8000/analyze/stream/${job_id}`
);

eventSource.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Status:', update.status, 'Progress:', update.progress);
  
  if (update.status === 'done') {
    console.log('Result:', update.result);
    eventSource.close();
  }
};

eventSource.onerror = (error) => {
  console.error('SSE Error:', error);
  eventSource.close();
};
```

## 📚 Documentation API

Une fois l'application lancée, visitez :

- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc

## 🔧 Résolution de problèmes

### Le modèle ne charge pas

```
Erreur : OutOfMemoryError
```

**Solution** : Réduire `MAX_PIXELS` dans config.py ou .env

```python
MAX_PIXELS=100000  # Au lieu de 151200
```

### Supabase ne se connecte pas

```
Erreur : SUPABASE_SERVICE_KEY a le rôle JWT 'anon'
```

**Solution** : Vous utilisez la mauvaise clé. Utilisez la clé **service_role** :
1. Allez dans Supabase Dashboard
2. Settings → API
3. Copiez la clé "service_role" (pas "anon")

### Les vidéos ne se téléchargent pas

```
Erreur : PrivateVideoError ou IPBlockedError
```

**Solutions** :
1. **Cookies** : Exportez vos cookies de navigateur
   ```bash
   # Chrome extension: Get cookies.txt LOCALLY
   # Puis dans .env :
   COOKIES_FILE=/path/to/cookies.txt
   ```

2. **Proxy** : Utilisez un proxy
   ```bash
   # Dans .env :
   PROXY_URL=http://your-proxy:8080
   ```

### Port déjà utilisé

```
Erreur : Address already in use
```

**Solution** : Changez le port
```bash
PORT=8001 python main.py
```

## 🎓 Prochaines étapes

1. **Lire la documentation complète** : `README.md`
2. **Comprendre l'architecture** : `ARCHITECTURE.md`
3. **Guide de migration** (si ancien code) : `MIGRATION.md`
4. **Ajouter des tests** : Voir `tests/test_example.py`
5. **Déployer en production** : Voir section ci-dessous

## 🚀 Déploiement

### Docker (recommandé)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t bombo-api .
docker run -p 8000:8000 --env-file .env bombo-api
```

### Production avec systemd

```ini
# /etc/systemd/system/bombo.service
[Unit]
Description=BOMBO Travel Video Analyzer API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/bombo
Environment="PATH=/opt/bombo/venv/bin"
ExecStart=/opt/bombo/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable bombo
sudo systemctl start bombo
sudo systemctl status bombo
```

### Avec nginx (reverse proxy)

```nginx
server {
    listen 80;
    server_name api.bombo.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # Important pour SSE
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        chunked_transfer_encoding off;
    }
}
```

## 📊 Monitoring

### Logs

```bash
# Voir les logs en temps réel
tail -f bombo.log

# Logs structurés avec loguru (optionnel)
pip install loguru
```

### Métriques (optionnel)

```python
# Ajouter prometheus-client
pip install prometheus-client

# Dans main.py
from prometheus_client import Counter, Histogram, make_asgi_app

requests_total = Counter('requests_total', 'Total requests')
response_time = Histogram('response_time_seconds', 'Response time')

# Mount /metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

## 🆘 Besoin d'aide ?

- 📖 Lisez `README.md` pour la documentation complète
- 🏗️ Consultez `ARCHITECTURE.md` pour comprendre le code
- 🔄 Voir `MIGRATION.md` si vous migrez depuis l'ancien code
- 🐛 Ouvrez une issue sur GitHub
- 💬 Contactez l'équipe de développement

## ✅ Checklist de production

Avant de déployer en production :

- [ ] Variables d'environnement sécurisées (pas de .env committé)
- [ ] Clé Supabase service_role (pas anon)
- [ ] CORS restreint aux domaines autorisés
- [ ] HTTPS activé (pas HTTP)
- [ ] Logs configurés
- [ ] Monitoring en place
- [ ] Backup de la base de données
- [ ] Tests passent
- [ ] Documentation à jour

Bon voyage avec BOMBO ! 🚀✈️
