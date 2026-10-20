"""
backend/api/routes.py
Endpoints REST FastAPI pour le système Agentic RAG Jurisprudence (TP2 + TP3 LangGraph).
"""
import json
import random
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.schemas import (
    SearchRequest, SearchResponse, SearchResultItem,
    AffaireDetail, SummaryRequest, SummaryResponse,
    ChatRequest, ChatResponse, SourceChunk, AgentStep, AgentMetrics
)
from backend.services.langchain_service import rag_service
from backend.services.agent_service import agent_service
from backend.services.data_service import data_service

api_router = APIRouter(prefix="/api")


@api_router.get("/health")
def health_check():
    """Vérifie l'état de l'API, le nombre d'affaires en mémoire et le statut du graphe LangGraph."""
    total_cases = data_service.count()
    return {
        "status": "healthy" if total_cases > 0 else "initializing",
        "cases_loaded": total_cases,
        "agentic_rag_enabled": True
    }


@api_router.post("/search", response_model=SearchResponse)
def search_cases(req: SearchRequest):
    """Recherche des décisions pertinentes (Hybride, BM25 ou Dense)."""
    results = rag_service.search_cases(query=req.query, top_k=req.top_k, mode=req.mode)
    items = [SearchResultItem(**r) for r in results]
    return SearchResponse(query=req.query, total_found=len(items), results=items)


@api_router.get("/cases/random")
def get_random_cases(limit: int = 30):
    """Retourne une sélection aléatoire d'affaires (métadonnées légères) pour l'exploration initiale."""
    all_cases = data_service.get_all()
    if not all_cases:
        return []
    k = min(limit, len(all_cases))
    sampled = random.sample(all_cases, k)
    items = []
    for c in sampled:
        item = dict(c)
        if "snippet" not in item or not item["snippet"]:
            item["snippet"] = (
                (item.get("solution") or "Décision du Tribunal judiciaire de Paris")
                + " rendue par le "
                + (item.get("chamber") or "Tribunal de Paris")
                + "."
            )
        items.append(item)
    return items


@api_router.get("/cases/{affaire_id}", response_model=AffaireDetail)
def get_case(affaire_id: str):
    """Retourne la fiche complète d'une affaire."""
    case = data_service.get_by_id(affaire_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Affaire {affaire_id} introuvable.")
    return AffaireDetail(**case)


@api_router.post("/summary", response_model=SummaryResponse)
def generate_summary(req: SummaryRequest):
    """
    Génère ou récupère le résumé juridique structuré (Faits, Procédure, Décision).
    Pattern Lazy-Loading Cache : 2ms si en cache, calcul LLM sinon.
    """
    case = data_service.get_by_id(req.affaire_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Affaire {req.affaire_id} introuvable.")

    try:
        parsed = rag_service.generate_summary(req.affaire_id, force_refresh=req.force_refresh)
        return SummaryResponse(
            affaire_id=req.affaire_id,
            faits=parsed["faits"],
            procedure=parsed["procedure"],
            decision=parsed["decision"],
            full_text_summary=parsed.get("full_text_summary", ""),
            is_cached=parsed.get("is_cached", False),
            cached_at=parsed.get("cached_at")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du résumé : {str(e)}")


@api_router.get("/summary/cache")
def get_summary_cache_stats():
    """Retourne l'état et les statistiques du cache persistant des résumés."""
    from backend.services.cache_service import summary_cache
    all_cached = summary_cache.list_all()
    return {
        "total_cached": len(all_cached),
        "cached_affaire_ids": list(all_cached.keys())
    }


@api_router.post("/chat", response_model=ChatResponse)
def chat_on_case(req: ChatRequest):
    """
    Endpoint principal du Chatbot Juridique (TP3 Agentic RAG par défaut, ou TP2 linéaire si use_agent=False).
    Supporte aussi bien une question sur un dossier précis (`affaire_id` fourni) qu'une question
    multi-étapes globale sur l'ensemble du corpus (`affaire_id=None`).
    """
    if req.affaire_id:
        case = data_service.get_by_id(req.affaire_id)
        if not case:
            raise HTTPException(status_code=404, detail=f"Affaire {req.affaire_id} introuvable.")

    try:
        if req.use_agent:
            result = agent_service.run_agent(
                question=req.question,
                affaire_id=req.affaire_id,
                thread_id=req.thread_id or f"thread_{req.affaire_id or 'global'}"
            )
            sources = [SourceChunk(**s) for s in result.get("sources", [])]
            trace_steps = [AgentStep(**step) for step in result.get("agent_trace", [])]
            metrics_obj = AgentMetrics(**result["metrics"]) if result.get("metrics") else None

            return ChatResponse(
                affaire_id=result.get("affaire_id") or req.affaire_id,
                question=req.question,
                answer=result["answer"],
                sources=sources,
                verification_status=result.get("verification_status", "SUFFISANT"),
                agent_trace=trace_steps,
                metrics=metrics_obj
            )
        else:
            if not req.affaire_id:
                raise HTTPException(status_code=400, detail="affaire_id est requis en mode RAG linéaire (use_agent=False).")
            result = rag_service.chat_on_case(affaire_id=req.affaire_id, question=req.question)
            sources = [SourceChunk(**s) for s in result["sources"]]
            return ChatResponse(
                affaire_id=req.affaire_id,
                question=req.question,
                answer=result["answer"],
                sources=sources,
                verification_status="SUFFISANT",
                agent_trace=[],
                metrics=None
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'exécution Agentic RAG : {str(e)}")


@api_router.post("/agent/stream")
def stream_agent_chat(req: ChatRequest):
    """
    Endpoint Server-Sent Events (SSE) streamant chaque étape du StateGraph LangGraph en temps réel :
    DECISION -> TOOL -> OBSERVATION -> CHECK -> FINAL.
    """
    def event_generator():
        try:
            for item in agent_service.stream_agent(
                question=req.question,
                affaire_id=req.affaire_id,
                thread_id=req.thread_id or f"thread_{req.affaire_id or 'global'}"
            ):
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
        except Exception as e:
            err_payload = {"event": "error", "detail": str(e)}
            yield f"data: {json.dumps(err_payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@api_router.get("/agent/graph")
def get_agent_graph_info():
    """
    Retourne le schéma Mermaid du StateGraph LangGraph (`draw_mermaid()`)
    ainsi que l'état de la mémoire longue (`InMemoryStore`).
    """
    return {
        "mermaid": agent_service.get_mermaid_graph(),
        "memory_store_profile": agent_service.get_memory_profile(),
        "max_iterations": 5,
        "tools": ["search_cases", "read_case", "external_search"]
    }
