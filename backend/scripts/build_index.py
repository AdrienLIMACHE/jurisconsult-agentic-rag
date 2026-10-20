"""
backend/scripts/build_index.py
Indexation vectorielle ChromaDB en streaming par lots de 10 affaires (Zero-RAM Overhead + Repos CPU).
"""
import sys
import time
import gc
import pickle
import argparse
from pathlib import Path
from tqdm import tqdm

# Sécurisation encodage Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
import pyarrow.parquet as pq
import chromadb

from backend.config import (
    SAMPLED_CORPUS_PATH, EMBEDDING_MODEL_NAME, CHROMA_DIR, 
    CHROMA_COLLECTION_NAME, BM25_INDEX_PATH,
    CHUNK_SIZE_CHARS, CHUNK_OVERLAP_CHARS
)


def extract_year(date_str: str) -> int:
    try:
        return int(str(date_str).split("-")[0])
    except Exception:
        return 2025


def build_index_streamed(
    limit: int = 5000, 
    batch_size: int = 10, 
    cooldown: float = 1.0,
    reset_db: bool = True
):
    print("=" * 65)
    print("🚀 DÉMARRAGE DE L'INDEXATION RAG (Streaming Parquet & Protection RAM/CPU)")
    print("=" * 65)
    print(f"[INFO] Configuration : Lots de {batch_size} affaires | Repos CPU = {cooldown}s | Limite = {limit}")

    if not SAMPLED_CORPUS_PATH.exists():
        raise FileNotFoundError(f"Fichier {SAMPLED_CORPUS_PATH} introuvable. Lancez prepare_data.py d'abord.")

    # 1. Préparation du splitter de texte récursif
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE_CHARS,
        chunk_overlap=CHUNK_OVERLAP_CHARS,
        separators=["\n\n", "\n", " ", ""]
    )

    # 2. Initialisation SentenceTransformerEmbeddings (384 dimensions)
    print(f"[INFO] Chargement du modèle SentenceTransformers ('{EMBEDDING_MODEL_NAME}')...")
    embeddings = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL_NAME)

    # 3. Initialisation persistante ChromaDB
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    if reset_db:
        try:
            client.delete_collection(CHROMA_COLLECTION_NAME)
            print(f"[INFO] Ancienne collection '{CHROMA_COLLECTION_NAME}' réinitialisée.")
        except Exception:
            pass

    vectorstore = Chroma(
        collection_name=CHROMA_COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(CHROMA_DIR),
        collection_metadata={"hnsw:space": "cosine"}
    )

    # 4. Lecture en streaming direct depuis le fichier Parquet (Zero RAM)
    parquet_file = pq.ParquetFile(SAMPLED_CORPUS_PATH)
    total_in_parquet = min(parquet_file.metadata.num_rows, limit)
    print(f"[INFO] Affaires à indexer : {total_in_parquet} (lecture par flux disque)")

    canonical_bm25_docs: list[Document] = []
    cases_processed = 0
    total_chunks_indexed = 0
    batch_num = 0

    columns_to_read = [
        "id", "number", "decision_date", "jurisdiction", 
        "chamber", "location", "solution", "text"
    ]

    with tqdm(total=total_in_parquet, desc="⚡ Streaming Indexation", unit="affaire") as pbar:
        for record_batch in parquet_file.iter_batches(batch_size=batch_size, columns=columns_to_read):
            if cases_processed >= limit:
                break

            batch_num += 1
            batch_df = record_batch.to_pandas()
            batch_records = batch_df.to_dict(orient="records")

            batch_chunks: list[Document] = []

            for case in batch_records:
                if cases_processed >= limit:
                    break

                case_id = str(case["id"])
                text = str(case.get("text", "") or "")
                if len(text.strip()) < 100:
                    cases_processed += 1
                    pbar.update(1)
                    continue

                location = str(case.get("location", "Tribunal judiciaire de Paris") or "")
                chamber = str(case.get("chamber", "Non spécifiée") or "")
                decision_date = str(case.get("decision_date", "") or "")
                number = str(case.get("number", "Non spécifié") or "")
                solution = str(case.get("solution", "Non précisée") or "")
                year = extract_year(decision_date)

                # Chapeau contextuel pour éviter le chunk orphelin
                context_header = (
                    f"[JURIDICTION : {location} | CHAMBRE : {chamber} | DATE : {decision_date}]\n"
                    f"[DISPOSITIF / SOLUTION : {solution[:200]}]\n\n"
                )

                # Niveau 1 : Document Canonique (Recherche globale)
                canonical_text = f"{context_header}--- EXPOSÉ DU LITIGE ET DISPOSITIF ---\n{text[:1200]}\n\n{text[-400:]}"
                canonical_meta = {
                    "affaire_id": case_id,
                    "chunk_id": f"{case_id}_canonical",
                    "chunk_index": 0,
                    "is_canonical": True,
                    "location": location,
                    "chamber": chamber,
                    "decision_date": decision_date,
                    "year": year,
                    "number": number,
                    "solution_short": solution[:200]
                }
                batch_chunks.append(Document(page_content=canonical_text, metadata=canonical_meta))
                canonical_bm25_docs.append(Document(page_content=canonical_text, metadata={"affaire_id": case_id}))

                # Niveau 2 : Chunks Détaillés (Chatbot Q&A)
                raw_chunks = splitter.split_text(text)
                for idx, c_text in enumerate(raw_chunks, 1):
                    contextualized_chunk = f"{context_header}--- EXTRAIT DU JUGEMENT (PARTIE {idx}) ---\n{c_text}"
                    chunk_meta = {
                        "affaire_id": case_id,
                        "chunk_id": f"{case_id}_c{idx}",
                        "chunk_index": idx,
                        "is_canonical": False,
                        "location": location,
                        "chamber": chamber,
                        "decision_date": decision_date,
                        "year": year,
                        "number": number,
                        "solution_short": solution[:200]
                    }
                    batch_chunks.append(Document(page_content=contextualized_chunk, metadata=chunk_meta))

                cases_processed += 1
                pbar.update(1)

            # Insertion vectorielle dans ChromaDB
            if batch_chunks:
                try:
                    vectorstore.add_documents(batch_chunks)
                    total_chunks_indexed += len(batch_chunks)
                except Exception as err:
                    print(f"\n[WARN] Erreur sur le lot {batch_num} : {err}")

            # Nettoyage mémoire immédiat (libère la RAM)
            del batch_df
            del batch_records
            del batch_chunks
            gc.collect()

            # Pause thermique CPU
            if cases_processed < total_in_parquet and cooldown > 0:
                pbar.set_postfix_str(f"Lot {batch_num} terminé | Repos CPU ({cooldown}s)")
                time.sleep(cooldown)

    # 5. Construction de l'index BM25
    print("\n[INFO] Construction et sauvegarde de l'index BM25...")
    bm25_retriever = BM25Retriever.from_documents(canonical_bm25_docs)
    BM25_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump(bm25_retriever, f)
    print(f"[SUCCESS] Index BM25 sauvegardé dans : {BM25_INDEX_PATH}")

    # Libération finale
    del canonical_bm25_docs
    gc.collect()

    print("\n" + "=" * 65)
    print(f"🎉 INDEXATION TERMINÉE EN TOUTE SÉCURITÉ !")
    print(f"   -> Affaires traitées   : {cases_processed}")
    print(f"   -> Chunks dans Chroma  : {total_chunks_indexed}")
    print(f"   -> Stockage ChromaDB   : {CHROMA_DIR.resolve()}")
    print("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Indexation RAG en streaming par lots (RAM sécurisée)")
    parser.add_argument("--limit", type=int, default=5000, help="Nombre max d'affaires à traiter")
    parser.add_argument("--batch-size", type=int, default=10, help="Nombre d'affaires lues et traitées par lot (défaut: 10)")
    parser.add_argument("--cooldown", type=float, default=1.0, help="Pause CPU en secondes entre les lots (défaut: 1.0)")
    args = parser.parse_args()

    build_index_streamed(
        limit=args.limit,
        batch_size=args.batch_size,
        cooldown=args.cooldown
    )
