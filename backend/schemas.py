"""
backend/schemas.py
Schémas Pydantic pour la validation des requêtes et réponses de l'API REST (TP2 + TP3 Agentic RAG).
"""
from typing import List, Optional
from pydantic import BaseModel, Field


# --- Recherche Globale ---
class SearchRequest(BaseModel):
    query: str = Field(..., description="Mots-clés ou requête en langage naturel", min_length=2)
    top_k: int = Field(default=30, ge=1, le=100, description="Nombre de décisions à retourner")
    mode: str = Field(default="hybrid", description="Mode : 'hybrid', 'bm25', ou 'dense'")


class SearchResultItem(BaseModel):
    id: str
    number: Optional[str] = None
    decision_date: Optional[str] = None
    jurisdiction: Optional[str] = None
    location: Optional[str] = None
    chamber: Optional[str] = None
    solution: Optional[str] = None
    snippet: str = Field(..., description="Extrait contextuel le plus pertinent")
    score: float = Field(default=0.0, description="Score de pertinence normalisé")


class SearchResponse(BaseModel):
    query: str
    total_found: int
    results: List[SearchResultItem]


# --- Affaire Détaillée ---
class AffaireDetail(BaseModel):
    id: str
    number: Optional[str] = None
    decision_date: Optional[str] = None
    jurisdiction: Optional[str] = None
    location: Optional[str] = None
    chamber: Optional[str] = None
    solution: Optional[str] = None
    text: str


# --- Résumé Juridique Structuré ---
class SummaryRequest(BaseModel):
    affaire_id: str = Field(..., description="ID de l'affaire à résumer")
    force_refresh: bool = Field(False, description="Forcer la régénération par le LLM même si en cache")


class SummaryResponse(BaseModel):
    affaire_id: str
    faits: str = Field(..., description="Exposé des faits du litige")
    procedure: str = Field(..., description="Historique de la procédure judiciaire")
    decision: str = Field(..., description="Solution / dispositif retenu")
    full_text_summary: str = Field(..., description="Résumé brut généré")
    is_cached: bool = Field(False, description="True si le résumé provient du cache instantané (2ms)")
    cached_at: Optional[str] = Field(None, description="Horodatage ISO de mise en cache")


# --- Traçabilité & Observabilité Agentic RAG (TP3 Section 4 & Section 9) ---
class AgentStep(BaseModel):
    step_type: str = Field(
        ...,
        description="Type d'étape standardisé : 'DECISION', 'TOOL', 'OBSERVATION', 'CHECK', ou 'FINAL'"
    )
    node: str = Field(..., description="Nom du nœud LangGraph ayant produit l'étape")
    title: str = Field(..., description="Titre synthétique de l'action ou décision")
    detail: str = Field(..., description="Détail opérationnel (arguments d'outil, extrait d'observation, statut CHECK)")
    iteration: int = Field(default=1, description="Numéro d'itération dans la boucle agentique")
    timestamp_ms: int = Field(default=0, description="Temps écoulé en ms depuis le début de la requête")


class AgentMetrics(BaseModel):
    iterations: int = Field(default=1, description="Nombre d'itérations effectuées dans le graphe (max 5)")
    llm_calls: int = Field(default=1, description="Nombre total d'appels au LLM local")
    tools_used: List[str] = Field(default=[], description="Liste ordonnée des outils appelés")
    verification_status: str = Field(default="SUFFISANT", description="Statut final du nœud CHECK")
    latency_s: float = Field(default=0.0, description="Temps d'exécution total en secondes")
    corpus_docs_count: int = Field(default=0, description="Nombre de preuves issues de [CORPUS_TP2]")
    external_docs_count: int = Field(default=0, description="Nombre de preuves issues de [SOURCE_EXTERNE]")
    active_case_id: Optional[str] = Field(default=None, description="Identifiant du dossier principal utilisé")


# --- Chatbot Q&A Agentique et Citations ---
class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' ou 'assistant'")
    content: str


class ChatRequest(BaseModel):
    affaire_id: Optional[str] = Field(default=None, description="ID de l'affaire (optionnel en mode recherche globale multi-étapes)")
    question: str = Field(..., description="Question posée par l'utilisateur", min_length=2)
    thread_id: Optional[str] = Field(default="session_default", description="Identifiant de session pour le checkpointer InMemorySaver")
    use_agent: bool = Field(default=True, description="True pour exécuter le graphe Agentic RAG (TP3), False pour le RAG linéaire (TP2)")
    chat_history: Optional[List[ChatMessage]] = Field(default=[], description="Historique de conversation facultatif")


class SourceChunk(BaseModel):
    chunk_index: int = Field(default=1, description="Indice du chunk dans le dossier ou numéro de source")
    text: str = Field(..., description="Passage exact extrait de la décision ou du texte de loi")
    score: Optional[float] = None
    source_type: str = Field(default="CORPUS_TP2", description="'CORPUS_TP2' ou 'SOURCE_EXTERNE'")
    affaire_id: Optional[str] = Field(default=None, description="ID du dossier si CORPUS_TP2")
    title: Optional[str] = Field(default=None, description="Titre de la source ou référence légale")


class ChatResponse(BaseModel):
    affaire_id: Optional[str] = None
    question: str
    answer: str = Field(..., description="Réponse de l'agent strictement fondée et sourcée ([CORPUS_TP2] / [SOURCE_EXTERNE])")
    sources: List[SourceChunk] = Field(default=[], description="Passages sources utilisés comme preuves")
    verification_status: str = Field(default="SUFFISANT", description="Résultat du nœud de vérification CHECK")
    agent_trace: List[AgentStep] = Field(default=[], description="Trace complète d'exécution du graphe LangGraph")
    metrics: Optional[AgentMetrics] = Field(default=None, description="Métriques d'observabilité de l'exécution")
