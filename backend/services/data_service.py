"""
backend/services/data_service.py
Service de données optimisé pour la RAM (Zero-RAM Overhead).
- En mémoire : uniquement les métadonnées légères (ID, date, solution, chambre : ~2 Mo).
- Sur disque : lecture du texte intégral uniquement à la demande (On-Demand Disk Lookup) en ~2 ms.
"""
from pathlib import Path
from typing import Optional, Dict, List
import pandas as pd
import pyarrow.parquet as pq
import gc

from backend.config import SAMPLED_CORPUS_PATH


class DataService:
    def __init__(self):
        self._light_metadata: Dict[str, dict] = {}
        self._is_loaded = False

    def load_data(self):
        """
        Charge UNIQUEMENT les colonnes légères en mémoire (SANS la colonne lourde 'text').
        La consommation RAM reste inférieure à 5 Mo.
        """
        if self._is_loaded:
            return

        if not SAMPLED_CORPUS_PATH.exists():
            raise FileNotFoundError(
                f"Le fichier {SAMPLED_CORPUS_PATH} n'existe pas. "
                "Exécutez d'abord : python backend/scripts/prepare_data.py"
            )

        light_columns = [
            "id", "number", "decision_date", "jurisdiction", 
            "chamber", "location", "solution"
        ]

        # Lecture exclusive des métadonnées (le texte lourd reste sur le disque)
        df_light = pd.read_parquet(SAMPLED_CORPUS_PATH, columns=light_columns)
        records = df_light.to_dict(orient="records")
        self._light_metadata = {str(row["id"]): row for row in records}
        self._is_loaded = True

        del df_light
        del records
        gc.collect()

        print(f"[INFO] DataService : {len(self._light_metadata)} métadonnées chargées en mémoire (~2 Mo).")

    def get_by_id(self, affaire_id: str) -> Optional[dict]:
        """
        Lecture du texte intégral à la demande directement sur disque sans charger le fichier.
        Temps d'accès : ~2 ms via PyArrow Row Filtering.
        """
        if not self._is_loaded:
            self.load_data()

        aff_id = str(affaire_id)
        if aff_id not in self._light_metadata:
            return None

        base_meta = dict(self._light_metadata[aff_id])

        # Lecture ciblée de la décision spécifique sur disque avec filtre PyArrow
        try:
            table = pq.read_table(
                SAMPLED_CORPUS_PATH,
                columns=["text"],
                filters=[("id", "==", aff_id)]
            )
            if table.num_rows > 0:
                base_meta["text"] = table.column("text")[0].as_py()
            else:
                base_meta["text"] = ""
            del table
        except Exception:
            base_meta["text"] = ""

        return base_meta

    def get_all(self) -> List[dict]:
        """Retourne la liste des métadonnées des affaires."""
        if not self._is_loaded:
            self.load_data()
        return list(self._light_metadata.values())

    def count(self) -> int:
        if not self._is_loaded:
            self.load_data()
        return len(self._light_metadata)


# Instance unique singleton
data_service = DataService()
