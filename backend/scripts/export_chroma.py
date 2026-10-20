"""
backend/scripts/export_chroma.py
Script d'exportation des données de ChromaDB (Documents + Métadonnées)
vers un fichier JSON pour audit qualité et vérification de la structure (reprise de Projet_CV).
"""
import sys
import json
from pathlib import Path

# Sécurisation encodage Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from backend.config import CHROMA_DIR, CHROMA_COLLECTION_NAME, DATA_DIR
import chromadb


def export_chroma_data(output_file: str = "data/chroma_dump.json") -> str:
    """
    Extrait l'ensemble des documents textuels et leurs métadonnées
    stockés dans la collection ChromaDB pour audit qualité.
    """
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        collection = client.get_collection(CHROMA_COLLECTION_NAME)
    except Exception as e:
        print(f"[WARN] Collection '{CHROMA_COLLECTION_NAME}' introuvable : {e}")
        return ""

    count = collection.count()
    print(f"[INFO] Nombre total de chunks dans ChromaDB : {count}")

    if count == 0:
        print("[WARN] La collection ChromaDB est vide. Lancez l'indexation d'abord.")
        return ""

    # Extraction des IDs, documents et métadonnées
    data = collection.get(include=["documents", "metadatas"])

    items = []
    for chunk_id, doc, meta in zip(data["ids"], data["documents"], data["metadatas"]):
        items.append({
            "id": chunk_id,
            "metadata": meta,
            "document": doc
        })

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_count": count,
            "exported_count": len(items),
            "items": items
        }, f, ensure_ascii=False, indent=2)

    print(f"[SUCCESS] Export réussi ! {len(items)} chunks enregistrés dans {output_path.resolve()}")
    return str(output_path.resolve())


if __name__ == "__main__":
    export_chroma_data()
