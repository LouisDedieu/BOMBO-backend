"""
Service de Machine Learning pour l'analyse de vidéos de voyage
"""
import torch
import json
import logging
import time
from typing import Tuple, Dict, Optional
from transformers import (
    Qwen2VLForConditionalGeneration,
    AutoProcessor,
    StoppingCriteria,
    StoppingCriteriaList,
)
from qwen_vl_utils import process_vision_info

from utils.prompts import TRAVEL_PROMPT, get_fallback_result

logger = logging.getLogger("bombo.ml_service")


class JSONClosedStopping(StoppingCriteria):
    """
    Arrête la génération dès que le modèle a produit un objet JSON complet,
    c'est-à-dire quand le nombre d'accolades ouvrantes { est égal au nombre
    d'accolades fermantes } et qu'au moins une a été ouverte.
    """

    def __init__(self, processor):
        super().__init__()
        self.processor = processor
        self._close_ids: set[int] = set()
        self._open_ids: set[int] = set()
        vocab = processor.tokenizer.get_vocab()
        for token, idx in vocab.items():
            cleaned = token.replace("▁", "").replace("Ġ", "").strip()
            if cleaned == "}":
                self._close_ids.add(idx)
            if cleaned == "{":
                self._open_ids.add(idx)

    def __call__(
        self,
        input_ids: torch.LongTensor,
        scores: torch.FloatTensor,
        **kwargs,
    ) -> bool:
        generated = input_ids[0].tolist()
        window = generated[-512:]
        opens = sum(1 for t in window if t in self._open_ids)
        closes = sum(1 for t in window if t in self._close_ids)
        return opens > 0 and closes >= opens


class MLService:
    """Service de gestion du modèle ML et de l'inférence"""

    def __init__(self):
        self.model: Optional[Qwen2VLForConditionalGeneration] = None
        self.processor: Optional[AutoProcessor] = None
        self.device: Optional[str] = None

    def load_model(self, model_id: str, max_pixels: int, fps: float):
        """Charge le modèle ML"""
        t0 = time.time()
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        logger.info("Chargement du modèle sur %s …", self.device.upper())

        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            device_map={"": self.device},
            attn_implementation="sdpa",
        )
        self.processor = AutoProcessor.from_pretrained(model_id)

        # Stocker les configs
        self.max_pixels = max_pixels
        self.fps = fps

        logger.info("Modèle prêt en %.2fs ✓", time.time() - t0)

    def unload_model(self):
        """Décharge le modèle de la mémoire"""
        del self.model, self.processor
        if self.device == "mps":
            torch.mps.empty_cache()
        logger.info("Modèle déchargé.")

    def is_ready(self) -> bool:
        """Vérifie si le modèle est chargé"""
        return self.model is not None and self.processor is not None

    def run_inference(
        self, video_path: str, max_new_tokens: int = 4096
    ) -> Tuple[Dict, float]:
        """
        Exécute l'inférence sur une vidéo.
        Retourne (résultat_dict, durée_secondes)
        """
        if not self.is_ready():
            raise RuntimeError("Le modèle n'est pas chargé")

        t0 = time.time()

        # Préparer les messages
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "video",
                        "video": video_path,
                        "max_pixels": self.max_pixels,
                        "fps": self.fps,
                    },
                    {
                        "type": "text",
                        "text": TRAVEL_PROMPT,
                    },
                ],
            }
        ]

        # Tokenisation
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = self.processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        ).to(self.device)

        # Critère d'arrêt
        stopping = StoppingCriteriaList([JSONClosedStopping(self.processor)])

        # Génération
        t_gen_start = time.time()
        with torch.inference_mode():
            generated_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                stopping_criteria=stopping,
            )
        duration = round(time.time() - t_gen_start, 2)
        tokens_generated = generated_ids.shape[-1] - inputs.input_ids.shape[-1]
        logger.info(
            "Generation terminee : %d tokens en %.2fs (%.1f tok/s)",
            tokens_generated,
            duration,
            tokens_generated / max(duration, 0.01),
        )

        # Décodage
        trimmed = [out[len(inp) :] for inp, out in zip(inputs.input_ids, generated_ids)]
        raw_text = self.processor.batch_decode(
            trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]

        logger.debug("Sortie brute du modele (%d cars) : %s", len(raw_text), raw_text[:300])

        # Extraction du JSON
        result = self._extract_json(raw_text)
        total_duration = round(time.time() - t0, 2)

        return result, total_duration

    def _extract_json(self, raw_text: str) -> Dict:
        """Extrait et parse le JSON de la sortie du modèle"""
        start_idx = raw_text.find("{")
        end_idx = raw_text.rfind("}") + 1

        if start_idx == -1 or end_idx == 0:
            logger.error("Aucun bloc JSON detecte dans la sortie du modele.")
            return get_fallback_result()

        json_str = raw_text[start_idx:end_idx]
        json_str = json_str.replace("\\'", "'")
        json_str = json_str.replace("\\n", " ")

        # Tentative de parsing JSON standard
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning("json.loads echoue (%s) -- tentative json-repair...", e)

        # Tentative avec json-repair
        try:
            from json_repair import repair_json

            repaired = repair_json(json_str, return_objects=True)
            if isinstance(repaired, dict) and "trip_title" in repaired:
                logger.info("JSON repare avec succes via json-repair.")
                return repaired
            logger.warning("json-repair n'a pas produit un dict valide : %s", type(repaired))
        except ImportError:
            logger.warning("json-repair non installe. Installez : pip install json-repair")
        except Exception as e:
            logger.warning("json-repair a echoue : %s", e)

        logger.error(
            "Toutes les tentatives de parsing ont echoue.\nSortie brute (%d cars) :\n%s",
            len(raw_text),
            raw_text[:800],
        )

        return get_fallback_result()


# Instance singleton
ml_service = MLService()
