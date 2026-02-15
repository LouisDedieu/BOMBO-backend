"""
Service SSE (Server-Sent Events) pour les mises à jour en temps réel
"""
import asyncio
import logging
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger("bombo.sse_service")


class JobManager:
    """Gestionnaire des jobs d'analyse avec support SSE"""

    def __init__(self):
        self.jobs: Dict[str, Dict] = {}

    def create_job(self, job_id: str) -> None:
        """Crée un nouveau job"""
        self.jobs[job_id] = {
            "status": "pending",
            "result": None,
            "error": None,
            "sse_queues": [],
        }
        logger.info(f"Job {job_id} créé")

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Récupère un job par son ID"""
        return self.jobs.get(job_id)

    def job_exists(self, job_id: str) -> bool:
        """Vérifie si un job existe"""
        return job_id in self.jobs

    def update_job_status(self, job_id: str, status: str, **kwargs) -> None:
        """Met à jour le statut d'un job"""
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = status
            self.jobs[job_id].update(kwargs)

    def add_sse_queue(self, job_id: str, queue: asyncio.Queue) -> None:
        """Ajoute une queue SSE pour un job"""
        if job_id in self.jobs:
            self.jobs[job_id]["sse_queues"].append(queue)

    def remove_sse_queue(self, job_id: str, queue: asyncio.Queue) -> None:
        """Retire une queue SSE d'un job"""
        if job_id in self.jobs and queue in self.jobs[job_id]["sse_queues"]:
            self.jobs[job_id]["sse_queues"].remove(queue)

    async def send_sse_update(
        self, job_id: str, status: str, data: Optional[Dict] = None
    ) -> None:
        """Envoie une mise à jour SSE à tous les clients connectés pour ce job"""
        if job_id not in self.jobs:
            return

        job = self.jobs[job_id]
        job["status"] = status

        message = {
            "job_id": job_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if data:
            message.update(data)

        if "sse_queues" in job:
            for queue in job["sse_queues"]:
                try:
                    await queue.put(message)
                except Exception as e:
                    logger.error(f"Erreur lors de l'envoi SSE pour job {job_id}: {e}")

    def cleanup_job(self, job_id: str) -> None:
        """Nettoie un job (optionnel, pour éviter la fuite mémoire)"""
        if job_id in self.jobs:
            # On garde le job pour permettre les requêtes de statut ultérieures
            # mais on vide les queues SSE
            self.jobs[job_id]["sse_queues"] = []


# Instance singleton
job_manager = JobManager()
