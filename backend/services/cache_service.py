"""
backend/services/cache_service.py
Service de gestion du cache persistant des résumés juridiques (Lazy-Loading Cache).
Stocke les résumés générés dans data/summaries_cache.json pour un accès instantané (2 ms).
"""
import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from backend.config import SUMMARIES_CACHE_PATH

logger = logging.getLogger(__name__)


class SummaryCacheService:
    """
    Gestionnaire thread-safe du cache persistant JSON des résumés d'affaires.
    Pattern : Lazy-Loading avec Fall-Through vers le LLM en cas de cache miss.
    """
    def __init__(self, cache_path: Path = SUMMARIES_CACHE_PATH):
        self.cache_path = Path(cache_path)
        self._lock = threading.Lock()
        self._ensure_cache_file()

    def _ensure_cache_file(self):
        """Crée le fichier de cache JSON initial s'il n'existe pas encore."""
        if not self.cache_path.exists():
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2, ensure_ascii=False)

    def _read_cache(self) -> Dict[str, Any]:
        """Lit l'intégralité du cache depuis le disque."""
        try:
            if not self.cache_path.exists():
                return {}
            with open(self.cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ Erreur lecture cache {self.cache_path}: {e}")
            return {}

    def get(self, affaire_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère un résumé mis en cache.
        Retourne le dictionnaire de résumé avec is_cached=True ou None si absent.
        """
        with self._lock:
            data = self._read_cache()
            item = data.get(str(affaire_id))
            if item:
                # Copie pour éviter toute modification accidentelle
                res = dict(item)
                res["is_cached"] = True
                return res
            return None

    def set(self, affaire_id: str, summary_data: Dict[str, Any]) -> None:
        """
        Enregistre ou met à jour un résumé dans le cache persistant JSON.
        """
        with self._lock:
            data = self._read_cache()
            entry = {
                "faits": summary_data.get("faits", "Non précisé"),
                "procedure": summary_data.get("procedure", "Non précisé"),
                "decision": summary_data.get("decision", "Non précisé"),
                "full_text_summary": summary_data.get("full_text_summary", ""),
                "cached_at": datetime.utcnow().isoformat() + "Z"
            }
            data[str(affaire_id)] = entry

            # Écriture propre avec encodage UTF-8 et indentation
            try:
                temp_file = self.cache_path.with_suffix(".tmp")
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                temp_file.replace(self.cache_path)
            except Exception as e:
                logger.error(f"❌ Échec écriture cache résumé {affaire_id} : {e}")

    def count(self) -> int:
        """Retourne le nombre total de résumés actuellement en cache."""
        with self._lock:
            return len(self._read_cache())

    def list_all(self) -> Dict[str, Any]:
        """Retourne l'ensemble des résumés en cache."""
        with self._lock:
            return self._read_cache()


# Singleton
summary_cache = SummaryCacheService()
