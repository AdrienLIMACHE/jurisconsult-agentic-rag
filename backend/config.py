"""
backend/config.py
Configuration centralisée du système Agentic RAG Jurisprudence (TP3 : LangGraph + Outils + Mémoire + Vérification).
Optimisé pour processeur Intel Pentium N3540 (4 cœurs, sans AVX2).
"""
from pathlib import Path
import os

# Chemins de base du projet
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_PATH = BASE_DIR / "antoinejeannot_jurisprudence" / "tribunal_judiciaire.parquet"
SAMPLED_CORPUS_PATH = DATA_DIR / "corpus_sampled.parquet"
CHROMA_DIR = BASE_DIR / "chroma_db"
BM25_INDEX_PATH = DATA_DIR / "bm25_index.pkl"
SUMMARIES_CACHE_PATH = DATA_DIR / "summaries_cache.json"

# Création automatique des dossiers si absents
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# Configuration Modèles
EMBEDDING_PROVIDER = "sentence-transformers"
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")

# Paramètres de Chunking
CHUNK_SIZE_CHARS = 1500        # ~350 mots
CHUNK_OVERLAP_CHARS = 200      # ~50 mots de chevauchement

# Paramètres Retrieval (Acquis TP2 : MRR = 0.967)
CHROMA_COLLECTION_NAME = "jurisprudence_chunks"
DEFAULT_TOP_K_SEARCH = 6
DEFAULT_TOP_K_CHAT = 2

# ==================== PARAMÈTRES AGENTIC RAG (TP3) ====================
AGENT_MAX_ITERATIONS = 5           # Garde-fou strict contre les boucles infinies (Section 3.3 du PDF)
AGENT_MEMORY_MAX_MESSAGES = 6      # Seuil de troncature/résumé de la mémoire courte (Ex. 8 Cours S2)
AGENT_DEFAULT_SEARCH_K = 4         # Nombre de décisions candidates retournées par search_cases
AGENT_READ_CASE_TOP_K = 2          # Nombre de chunks structurels retournés par read_case (optimisé CPU N3540)
ENABLE_EXTERNAL_WEB_SEARCH = True  # Active le fallback web en complément du référentiel légal certifié

# Protection Thermique CPU & Cadencement par Lots (Pattern Projet_CV)
INDEXING_BATCH_SIZE = 5            # 5 affaires par lot
COOLDOWN_BETWEEN_BATCHES = 1.0     # Pause thermique en secondes entre les lots

# Paramètres Serveur FastAPI
HOST = "0.0.0.0"
PORT = 8000
