"""
backend/scripts/prepare_data.py
Script d'échantillonnage cohérent : 5 000 décisions récentes du Tribunal judiciaire de Paris.
"""
import sys
from pathlib import Path

# Sécurisation de l'encodage de la console Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import pandas as pd

# Ajout de la racine au sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from backend.config import RAW_DATA_PATH, SAMPLED_CORPUS_PATH


def prepare_sample(sample_size: int = 5000, target_location: str = "Tribunal judiciaire de Paris"):
    print(f"[INFO] Lecture du fichier source : {RAW_DATA_PATH} ...")
    if not RAW_DATA_PATH.exists():
        raise FileNotFoundError(f"Le fichier {RAW_DATA_PATH} est introuvable. Téléchargez-le d'abord.")

    columns_to_keep = [
        "id", "number", "decision_date", "jurisdiction", 
        "chamber", "location", "solution", "text"
    ]

    # Lecture ciblée des colonnes requises
    df = pd.read_parquet(RAW_DATA_PATH, columns=columns_to_keep)
    total_initial = len(df)
    print(f"[INFO] Total décisions chargées : {total_initial}")

    # 1. Filtrage sur le Tribunal judiciaire de Paris
    print(f"[INFO] Filtrage sur la juridiction : '{target_location}'...")
    df_paris = df[df["location"] == target_location].copy()
    print(f"[INFO] Décisions trouvées pour Paris : {len(df_paris)}")

    # 2. Nettoyage : suppression des textes nuls ou trop courts (< 300 caractères)
    df_paris = df_paris.dropna(subset=["text"])
    df_paris = df_paris[df_paris["text"].str.strip().str.len() > 300]
    print(f"[INFO] Décisions valides après nettoyage textuel : {len(df_paris)}")

    # 3. Traitement des valeurs manquantes dans les métadonnées utiles
    df_paris["number"] = df_paris["number"].fillna("Numéro non spécifié")
    df_paris["chamber"] = df_paris["chamber"].fillna("Chambre non spécifiée")
    df_paris["solution"] = df_paris["solution"].fillna("Solution non précisée")
    df_paris["jurisdiction"] = df_paris["jurisdiction"].fillna("Tribunal Judiciaire")

    # 4. Tri par date décroissante pour retenir les 5 000 plus récentes
    df_paris["parsed_date"] = pd.to_datetime(df_paris["decision_date"], errors="coerce")
    df_sorted = df_paris.sort_values(by="parsed_date", ascending=False)

    df_sample = df_sorted.head(sample_size).copy()
    df_sample = df_sample.drop(columns=["parsed_date"])

    # 5. Sauvegarde
    SAMPLED_CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_sample.to_parquet(SAMPLED_CORPUS_PATH, index=False)

    print(f"[SUCCESS] Échantillon de {len(df_sample)} affaires sauvegardé dans : {SAMPLED_CORPUS_PATH}")
    file_size_mb = SAMPLED_CORPUS_PATH.stat().st_size / (1024 * 1024)
    print(f"[INFO] Taille du fichier produit : {file_size_mb:.2f} Mo")
    print(f"[INFO] Dates couvertes : de {df_sample['decision_date'].min()} à {df_sample['decision_date'].max()}")


if __name__ == "__main__":
    prepare_sample(sample_size=5000, target_location="Tribunal judiciaire de Paris")
