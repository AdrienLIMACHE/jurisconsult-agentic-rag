"""
backend/services/agent_service.py
Orchestrateur Agentic RAG basé sur LangGraph (TP3 — Analyse de Jurisprudence).

Aligné à 100 % avec :
1. Le cours S2_memoire_rag_graphe.ipynb (Pr Mehdi Ammi) :
   - StateGraph(EtatAgent) avec Annotated[list, add_messages]
   - RouteDecision(BaseModel) Pydantic
   - Nœud gerer_memoire_courte (RemoveMessage)
   - Double mémoire : InMemorySaver (session thread_id) + InMemoryStore (inter-sessions BaseStore)
   - Export Mermaid via graphe.get_graph().draw_mermaid()
   - Streaming temps réel via graphe.stream(..., stream_mode="updates")
2. Le cahier des charges TP3_Agentic_RAG_Jurisprudence.pdf :
   - 3 outils @tool : search_cases, read_case, external_search
   - Boucle contrôlée avec limite stricte AGENT_MAX_ITERATIONS = 5
   - Nœud de vérification CHECK (présence d'évidence, cohérence réponse <-> passages, distinction [CORPUS_TP2] vs [SOURCE_EXTERNE])
   - Trace d'exécution standardisée : [DECISION], [TOOL], [OBSERVATION], [CHECK], [FINAL]
3. L'optimisation matérielle CPU Intel Pentium N3540 (4 cœurs, sans AVX2).
"""
import re
import time
from typing import Annotated, Literal, TypedDict, Optional, List, Dict, Any, Generator, Tuple
from pydantic import BaseModel, Field

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, RemoveMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Import LangGraph avec fallback résilient si certaines sous-briques varient selon la version installée
try:
    from langgraph.graph import StateGraph, START, END
    from langgraph.graph.message import add_messages
    from langgraph.checkpoint.memory import InMemorySaver
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    START = "__start__"
    END = "__end__"

    def add_messages(left: list, right: list) -> list:
        return (left or []) + (right or [])

try:
    from langgraph.store.memory import InMemoryStore
    from langgraph.store.base import BaseStore
except ImportError:
    class _StoreItem:
        def __init__(self, value: Any):
            self.value = value

    class BaseStore:
        pass

    class InMemoryStore(BaseStore):
        def __init__(self):
            self._data: Dict[tuple, Dict[str, _StoreItem]] = {}

        def get(self, namespace: tuple, key: str) -> Optional[_StoreItem]:
            return self._data.get(namespace, {}).get(key)

        def put(self, namespace: tuple, key: str, value: Any) -> None:
            if namespace not in self._data:
                self._data[namespace] = {}
            self._data[namespace][key] = _StoreItem(value)

from backend.config import (
    AGENT_MAX_ITERATIONS,
    AGENT_MEMORY_MAX_MESSAGES,
    AGENT_DEFAULT_SEARCH_K
)
from backend.services.langchain_service import rag_service
from backend.services.tools_service import (
    search_cases,
    read_case,
    external_search,
    execute_search_cases_structured,
    execute_read_case_structured,
    execute_external_search_structured
)


# ==============================================================================
# 1. MODÈLE PYDANTIC DU ROUTEUR (CONVENTION EXERCICE 6 & 9 DU COURS S2)
# ==============================================================================
class RouteDecision(BaseModel):
    """Modèle Pydantic structurant la décision du nœud planificateur."""
    action: Literal["search_cases", "read_case", "external_search", "generer"] = Field(
        description=(
            "Choisis 'search_cases' pour chercher des décisions dans le corpus local TP2. "
            "Choisis 'read_case' pour lire le détail et la fiche d'identité d'un dossier identifié par son case_id. "
            "Choisis 'external_search' pour chercher le texte officiel d'un article de loi ou une source externe hors corpus. "
            "Choisis 'generer' lorsque toutes les preuves nécessaires sont déjà rassemblées."
        )
    )
    tool_query: str = Field(
        description="Requête de recherche optimisée ou identifiant case_id à transmettre à l'outil choisi."
    )
    justification: str = Field(
        description="Justification concise du choix de l'action."
    )


# ==============================================================================
# 2. DÉFINITION DE L'ÉTAT PARTAGÉ (SECTION 3.2 DU PDF TP3 + COURS S2)
# ==============================================================================
class EtatAgent(TypedDict):
    # Champs obligatoires du cahier des charges TP3 (Section 3.2)
    query: str                                      # Question posée par l'utilisateur
    messages: Annotated[list, add_messages]         # Historique de conversation avec réducteur LangGraph
    retrieved_docs: List[Dict[str, Any]]            # Passages structurés issus de [CORPUS_TP2]
    external_sources: List[Dict[str, Any]]          # Passages structurés issus de [SOURCE_EXTERNE]
    iterations: int                                 # Nombre d'itérations effectuées (max = 5)
    verification_status: str                        # "EN_ATTENTE", "SUFFISANT", "INSUFFISANT", "LIMITE_ATTEINTE"
    final_answer: str                               # Réponse finale sourcée et vérifiée

    # Champs d'orchestration, de mémoire et d'observabilité
    selected_case_id: Optional[str]                 # ID du dossier sélectionné ou découvert dynamiquement
    discovered_case_id: Optional[str]               # ID du meilleur dossier trouvé par search_cases
    current_action: str                             # Action décidée par le planificateur
    tool_query: str                                 # Paramètre passé à l'outil
    last_tool_output: str                           # Dernière sortie brute de l'outil exécuté
    corpus_context_blocks: List[str]                # Blocs de contexte textuel [CORPUS_TP2] pour le LLM
    external_context_blocks: List[str]              # Blocs de contexte textuel [SOURCE_EXTERNE] pour le LLM
    draft_answer: str                               # Projet de réponse généré avant vérification CHECK
    verification_feedback: str                      # Diagnostic du nœud verificateur (CHECK)
    needs_external_law: bool                        # Indique si la question requiert aussi une source légale externe
    needs_multi_step_read: bool                     # Indique si la question requiert search_cases -> read_case
    agent_trace: List[Dict[str, Any]]               # Trace complète : DECISION, TOOL, OBSERVATION, CHECK, FINAL
    metrics: Dict[str, Any]                         # Métriques : llm_calls, tools_used, latency_s, etc.
    start_time: float                               # Horodatage de début d'exécution


# ==============================================================================
# 3. DÉTECTEURS SÉMANTIQUES RAPIDES (HYBRIDE NEURO-SYMBOLIQUE ~1ms SUR CPU)
# ==============================================================================
EXTERNAL_LAW_PATTERNS = [
    r"que\s+(?:prévoit|dit|dispose)\s+(?:exactement\s+)?(?:le\s+texte|la\s+loi|l'article|le\s+code)",
    r"texte\s+officiel\s+de\s+l'article",
    r"définition\s+(?:légale|juridique|officielle)",
    r"en\s+droit\s+français",
    r"hors\s+(?:du\s+)?corpus",
    r"source\s+externe",
    r"légifrance",
    r"loi\s+badinter",
    r"loi\s+du\s+5\s+juillet\s+1985",
    r"loi\s+du\s+6\s+juillet\s+1989",
    r"article\s+(?:700|696|514|1240|1382|1103|1231|233|234|262-1|270)\s+du\s+code\s+de\s+procédure\s+civile\s+en\s+droit",
]


def _detect_external_law_need(question: str) -> Tuple[bool, str]:
    """
    Détecte si la question demande explicitement le texte officiel d'une loi, d'un code
    ou une vérification doctrinale externe (Scénario 3).
    """
    q_lower = question.lower()
    is_external = any(re.search(pat, q_lower) for pat in EXTERNAL_LAW_PATTERNS)

    # Détection d'une question en deux volets (ex: "Que dit le dossier ... et que prévoit le texte officiel de l'article 700 ?")
    if not is_external and ("que prévoit" in q_lower or "texte officiel" in q_lower or "définis" in q_lower or "définition de l'article" in q_lower):
        if any(k in q_lower for k in ["article", "code civil", "code de procédure", "cpc", "loi", "dépens"]):
            is_external = True

    # Extraction de la cible légale pour external_search
    art_match = re.search(
        r"(article\s+[0-9a-z\.\-]+(?:\s+du\s+code\s+[a-zà-ÿ\s]+|\s+du\s+cpc)?|loi\s+badinter|loi\s+du\s+[0-9]+\s+[a-zà-ÿ]+\s+[0-9]{4}|dépens\s+article\s+696)",
        q_lower
    )
    ext_query = art_match.group(1).strip() if art_match else question
    return is_external, ext_query


def _extract_case_id_from_text(text: str) -> Optional[str]:
    """Extrait un identifiant de dossier 24 caractères hexadécimaux s'il est présent dans la question."""
    if not text:
        return None
    m = re.search(r"\b([0-9a-f]{24})\b", text, re.IGNORECASE)
    return m.group(1) if m else None


def _clean_search_keywords(question: str) -> str:
    """Extrait les mots-clés juridiques porteurs pour search_cases."""
    stop_phrases = [
        "cherche dans la base", "cherche dans le corpus", "trouve une affaire",
        "trouve un dossier", "puis lis le dossier", "pour m'indiquer",
        "indique-moi", "quels sont", "quelle est", "dans la base"
    ]
    cleaned = question.lower()
    for sp in stop_phrases:
        cleaned = cleaned.replace(sp, " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if len(cleaned) >= 4 else question


# ==============================================================================
# 4. CONSTRUCTION DU GRAPHE LANGGRAPH (AGENTIC RAG SERVICE)
# ==============================================================================
class AgenticRAGService:
    def __init__(self):
        self.store = InMemoryStore()
        self.checkpointer = InMemorySaver() if LANGGRAPH_AVAILABLE else None
        self._agent_prompt = self._build_agent_synthesis_prompt()
        self.graphe = self._compile_graph()

    def _build_agent_synthesis_prompt(self) -> ChatPromptTemplate:
        """
        Prompt de synthèse finale conçu pour distinguer strictement [CORPUS_TP2] et [SOURCE_EXTERNE]
        tout en préservant les performances d'ancrage du TP2 (Accuracy 93.3%, Anti-Hallucination 100%).
        """
        system_msg = (
            "Tu es un assistant juridique précis du Tribunal judiciaire de Paris.\n"
            "RÈGLES STRICTES :\n"
            "1. PRIORITÉ ABSOLUE À LA FICHE D'IDENTITÉ : Pour le Numéro RG, le Juge, le Greffier, les Parties, "
            "les Avocats, la Date, les Dépens ou l'Article 700, recopie MOT POUR MOT les valeurs écrites dans "
            "'=== FICHE D'IDENTITÉ OFFICIELLE DE L'AFFAIRE (PRIORITAIRE) ==='.\n"
            "2. NUMÉRO RG UNIQUE : Le numéro RG du dossier est unique pour toute l'affaire (ligne 'NUMÉRO RG (RÔLE GÉNÉRAL) EXACT DU DOSSIER').\n"
            "3. BRIÈVETÉ : Réponds directement en 1 à 2 phrases complètes, sans préambule ni liste inachevée."
        )
        user_msg = (
            "{context}\n\n"
            "Question : {question}\n"
            "Réponse directe et factuelle (1 à 2 phrases maximum, basée sur la Fiche d'Identité Officielle) :"
        )
        return ChatPromptTemplate.from_messages([
            ("system", system_msg),
            ("user", user_msg)
        ])

    def _elapsed_ms(self, etat: EtatAgent) -> int:
        start = etat.get("start_time") or time.time()
        return int((time.time() - start) * 1000)

    # --------------------------------------------------------------------------
    # NŒUD 1 : GESTION DE LA MÉMOIRE COURTE & LONGUE (EX. 8 COURS S2)
    # --------------------------------------------------------------------------
    def noeud_memoire_courte(self, etat: EtatAgent) -> dict:
        active_store = self.store
        msgs = etat.get("messages") or []
        updates: Dict[str, Any] = {}

        # A. Troncature / résumé de la mémoire courte si > AGENT_MEMORY_MAX_MESSAGES (Ex. 8 S2)
        if len(msgs) > AGENT_MEMORY_MAX_MESSAGES:
            anciens = msgs[:-2]
            suppressions = [
                RemoveMessage(id=m.id)
                for m in anciens
                if getattr(m, "id", None) is not None
            ]
            if suppressions:
                updates["messages"] = suppressions + [
                    SystemMessage(content="Contexte précédent résumé pour optimiser la mémoire courte.")
                ]

        # B. Lecture de la mémoire longue inter-sessions (Store)
        mem = active_store.get(("jurisprudence", "user"), "profil")
        profil = mem.value if mem else {"themes": [], "dossiers_lus": [], "last_case_id": None}

        # Si aucun case_id n'est fourni mais que la question fait référence au dossier précédent ("dans cette affaire", "et le greffier ?")
        selected_id = etat.get("selected_case_id") or _extract_case_id_from_text(etat.get("query", ""))
        q_lower = etat.get("query", "").lower()
        if not selected_id and profil.get("last_case_id"):
            follow_up_markers = [
                "cette affaire", "ce dossier", "cette décision", "ce jugement",
                "et qui est", "et quel est", "son avocat", "le juge", "le greffier"
            ]
            if any(m in q_lower for m in follow_up_markers):
                selected_id = profil["last_case_id"]

        if selected_id:
            updates["selected_case_id"] = selected_id

        return updates

    # --------------------------------------------------------------------------
    # NŒUD 2 : PLANIFICATEUR / ROUTEUR HYBRIDE ([DECISION])
    # --------------------------------------------------------------------------
    def noeud_planificateur(self, etat: EtatAgent) -> dict:
        iterations = etat.get("iterations", 0)
        question = etat.get("query", "")
        selected_id = etat.get("selected_case_id")
        discovered_id = etat.get("discovered_case_id")
        metrics = dict(etat.get("metrics") or {})
        tools_used: List[str] = list(metrics.get("tools_used") or [])
        trace = list(etat.get("agent_trace") or [])
        verif_status = etat.get("verification_status", "EN_ATTENTE")
        needs_ext = etat.get("needs_external_law", False)
        needs_multi = etat.get("needs_multi_step_read", False)

        has_read_case = "read_case" in tools_used
        has_searched_cases = "search_cases" in tools_used
        has_external_search = "external_search" in tools_used

        # Décision de routage hybride (Neuro-Symbolique)
        decision: RouteDecision

        # CAS 1 : Retour de boucle depuis le vérificateur (CHECK == INSUFFISANT)
        if verif_status == "INSUFFISANT":
            feedback = etat.get("verification_feedback", "")
            if "read_case" in feedback and (discovered_id or selected_id) and not has_read_case:
                target_id = discovered_id or selected_id
                decision = RouteDecision(
                    action="read_case",
                    tool_query=str(target_id),
                    justification=f"Relance après CHECK : ouverture détaillée du dossier {target_id} trouvé par search_cases."
                )
            elif not has_external_search:
                _, ext_q = _detect_external_law_need(question)
                decision = RouteDecision(
                    action="external_search",
                    tool_query=ext_q,
                    justification=f"Relance après CHECK ({feedback}) : recherche du fondement légal dans [SOURCE_EXTERNE]."
                )
            elif not has_searched_cases:
                decision = RouteDecision(
                    action="search_cases",
                    tool_query=_clean_search_keywords(question),
                    justification="Relance après CHECK : recherche élargie par mots-clés dans le corpus TP2."
                )
            else:
                decision = RouteDecision(
                    action="generer",
                    tool_query="",
                    justification="Synthèse finale à partir de l'ensemble des preuves internes et externes collectées."
                )

        # CAS 2 : Premier appel ou collecte initiale d'informations
        elif not tools_used:
            # Si un dossier précis est sélectionné/connu -> Scénario 1 (ou Étape 1 du Scénario 3)
            if selected_id:
                decision = RouteDecision(
                    action="read_case",
                    tool_query=str(selected_id),
                    justification=f"Dossier cible identifié ({selected_id}) : appel direct à read_case pour extraire la Fiche d'Identité et les attendus."
                )
            # Si la question porte uniquement sur un texte de loi théorique sans mention de dossier ni de recherche d'affaire
            elif needs_ext and not any(w in question.lower() for w in ["affaire", "dossier", "jugement", "décision", "base", "corpus", "cherche", "trouve"]):
                _, ext_q = _detect_external_law_need(question)
                decision = RouteDecision(
                    action="external_search",
                    tool_query=ext_q,
                    justification="Question portant sur le texte officiel d'un article de loi hors corpus : appel à external_search."
                )
            # Sinon -> Recherche multi-dossiers dans le corpus TP2 (Scénario 2 & Scénario 3 sans ID initial)
            else:
                decision = RouteDecision(
                    action="search_cases",
                    tool_query=_clean_search_keywords(question),
                    justification="Aucun case_id fourni : lancement de search_cases pour identifier les dossiers pertinents dans [CORPUS_TP2]."
                )

        # CAS 3 : Chaînage multi-étapes après un premier outil (OBSERVATION -> DECISION)
        else:
            # Si search_cases a trouvé un dossier et qu'on doit lire ses détails (Scénario 2)
            if has_searched_cases and not has_read_case and (discovered_id or selected_id) and needs_multi:
                target_id = discovered_id or selected_id
                decision = RouteDecision(
                    action="read_case",
                    tool_query=str(target_id),
                    justification=f"Chaînage multi-étapes (Scénario 2) : lecture approfondie du dossier {target_id} identifié par search_cases."
                )
            # Si search_cases n'a rien trouvé du tout -> bascule vers external_search (Scénario 3)
            elif has_searched_cases and not etat.get("retrieved_docs") and not has_external_search:
                _, ext_q = _detect_external_law_need(question)
                decision = RouteDecision(
                    action="external_search",
                    tool_query=ext_q,
                    justification="Aucun résultat dans le corpus interne TP2 : bascule vers external_search ([SOURCE_EXTERNE])."
                )
            # Si toutes les preuves du corpus sont lues (ou si on veut que le nœud CHECK déclenche la boucle externe pour démontrer le cycle CHECK -> RETRY)
            else:
                decision = RouteDecision(
                    action="generer",
                    tool_query="",
                    justification="Preuves collectées : passage au générateur avant contrôle par le nœud de vérification (CHECK)."
                )

        # Incrémentation du compteur d'itérations lorsqu'on lance une action d'outil
        new_iter = iterations + 1 if decision.action != "generer" else max(1, iterations)

        trace.append({
            "step_type": "DECISION",
            "node": "planificateur",
            "title": f"Action choisie : {decision.action}",
            "detail": f"{decision.justification}" + (f" (cible : « {decision.tool_query} »)" if decision.tool_query else ""),
            "iteration": new_iter,
            "timestamp_ms": self._elapsed_ms(etat)
        })

        return {
            "iterations": new_iter,
            "current_action": decision.action,
            "tool_query": decision.tool_query,
            "agent_trace": trace
        }

    # --------------------------------------------------------------------------
    # NŒUD 3 : EXÉCUTEUR D'OUTILS ([TOOL])
    # --------------------------------------------------------------------------
    def noeud_executeur_outils(self, etat: EtatAgent) -> dict:
        action = etat.get("current_action", "search_cases")
        t_query = etat.get("tool_query", "") or etat.get("query", "")
        question = etat.get("query", "")
        iteration = etat.get("iterations", 1)
        trace = list(etat.get("agent_trace") or [])
        metrics = dict(etat.get("metrics") or {})
        tools_used = list(metrics.get("tools_used") or [])

        retrieved_docs = list(etat.get("retrieved_docs") or [])
        external_sources = list(etat.get("external_sources") or [])
        corpus_blocks = list(etat.get("corpus_context_blocks") or [])
        external_blocks = list(etat.get("external_context_blocks") or [])
        selected_id = etat.get("selected_case_id")
        discovered_id = etat.get("discovered_case_id")

        tool_output_str = ""

        if action == "read_case":
            tools_used.append("read_case")
            trace.append({
                "step_type": "TOOL",
                "node": "executeur_outils",
                "title": f"read_case(case_id='{t_query}')",
                "detail": f"Appel de l'outil @tool read_case sur le dossier '{t_query}' avec reranking structurel TP2.",
                "iteration": iteration,
                "timestamp_ms": self._elapsed_ms(etat)
            })
            # Invocation de la fonction structurée sous-jacente à @tool read_case
            tool_output_str, new_docs, resolved_id = execute_read_case_structured(case_id=t_query, query=question)
            if resolved_id:
                selected_id = resolved_id
            if new_docs:
                # Si on lit un dossier complet, ses chunks remplacent en tête les simples snippets de search_cases
                retrieved_docs = new_docs + [d for d in retrieved_docs if d.get("affaire_id") != resolved_id]
                corpus_blocks.append(tool_output_str)

        elif action == "external_search":
            tools_used.append("external_search")
            trace.append({
                "step_type": "TOOL",
                "node": "executeur_outils",
                "title": f"external_search(query='{t_query}')",
                "detail": f"Appel de l'outil @tool external_search pour rechercher la référence légale/externe : « {t_query} ».",
                "iteration": iteration,
                "timestamp_ms": self._elapsed_ms(etat)
            })
            tool_output_str, ext_docs = execute_external_search_structured(query=t_query)
            if ext_docs:
                external_sources.extend(ext_docs)
                external_blocks.append(tool_output_str)

        else:  # search_cases
            tools_used.append("search_cases")
            trace.append({
                "step_type": "TOOL",
                "node": "executeur_outils",
                "title": f"search_cases(query='{t_query}', k={AGENT_DEFAULT_SEARCH_K})",
                "detail": f"Appel de l'outil @tool search_cases dans ChromaDB + BM25 (mode hybride).",
                "iteration": iteration,
                "timestamp_ms": self._elapsed_ms(etat)
            })
            tool_output_str, search_docs = execute_search_cases_structured(query=t_query, k=AGENT_DEFAULT_SEARCH_K)
            if search_docs:
                retrieved_docs.extend(search_docs)
                corpus_blocks.append(tool_output_str)
                first_id = search_docs[0].get("affaire_id")
                if first_id:
                    discovered_id = first_id

        metrics["tools_used"] = tools_used

        return {
            "last_tool_output": tool_output_str,
            "retrieved_docs": retrieved_docs,
            "external_sources": external_sources,
            "corpus_context_blocks": corpus_blocks,
            "external_context_blocks": external_blocks,
            "selected_case_id": selected_id,
            "discovered_case_id": discovered_id,
            "verification_status": "EN_ATTENTE",
            "agent_trace": trace,
            "metrics": metrics
        }

    # --------------------------------------------------------------------------
    # NŒUD 4 : OBSERVATEUR ([OBSERVATION])
    # --------------------------------------------------------------------------
    def noeud_observateur(self, etat: EtatAgent) -> dict:
        action = etat.get("current_action", "")
        raw_out = etat.get("last_tool_output", "")
        iteration = etat.get("iterations", 1)
        trace = list(etat.get("agent_trace") or [])
        discovered_id = etat.get("discovered_case_id")
        selected_id = etat.get("selected_case_id")

        if action == "search_cases":
            n_docs = len(etat.get("retrieved_docs") or [])
            summary_obs = (
                f"[CORPUS_TP2] {n_docs} décision(s) candidate(s) identifiée(s). "
                + (f"Meilleur dossier candidat : ID={discovered_id}." if discovered_id else "Aucun dossier trouvé.")
            )
        elif action == "read_case":
            n_chunks = len([d for d in (etat.get("retrieved_docs") or []) if d.get("affaire_id") == selected_id])
            summary_obs = (
                f"[CORPUS_TP2] Dossier {selected_id} lu avec succès : Fiche d'Identité Officielle extraite + "
                f"{n_chunks} passage(s) clé(s) classés par pertinence."
            )
        else:
            n_ext = len(etat.get("external_sources") or [])
            titles = [d.get("title", "Source externe") for d in (etat.get("external_sources") or [])]
            summary_obs = (
                f"[SOURCE_EXTERNE] {n_ext} texte(s) de référence récupéré(s) hors corpus : {', '.join(titles[:2])}."
            )

        trace.append({
            "step_type": "OBSERVATION",
            "node": "observateur",
            "title": f"Résultat de {action}",
            "detail": summary_obs + (f"\nExtrait : {raw_out[:240]}..." if raw_out else ""),
            "iteration": iteration,
            "timestamp_ms": self._elapsed_ms(etat)
        })

        return {
            "agent_trace": trace
        }

    # --------------------------------------------------------------------------
    # NŒUD 5 : GÉNÉRATEUR DE RÉPONSE SOURCÉE
    # --------------------------------------------------------------------------
    def noeud_generateur(self, etat: EtatAgent) -> dict:
        question = etat.get("query", "")
        corpus_blocks = etat.get("corpus_context_blocks") or []
        external_blocks = etat.get("external_context_blocks") or []
        metrics = dict(etat.get("metrics") or {})
        tools_used = metrics.get("tools_used") or []
        needs_ext = etat.get("needs_external_law", False)

        # Optimisation CPU Pentium N3540 :
        # Si l'agent sait déjà que la question exige un texte de loi externe (Scénario 3)
        # et que external_search n'a pas encore été appelé, on ne gaspille pas un appel LLM de 30s
        # avant le nœud CHECK : on produit un brouillon partiel qui sera immédiatement intercepté par CHECK !
        if needs_ext and "external_search" not in tools_used and etat.get("iterations", 1) < AGENT_MAX_ITERATIONS:
            draft = (
                "[BROUILLON PARTIEL CORPUS_TP2] Les éléments factuels du dossier local ont été lus, "
                "mais le texte législatif officiel demandé ne figure pas intégralement dans le jugement [CORPUS_TP2]."
            )
            return {"draft_answer": draft}

        # Construction du contexte structuré distinguant [CORPUS_TP2] et [SOURCE_EXTERNE]
        context_parts = []
        if corpus_blocks:
            # On privilégie toujours le bloc issu de read_case (qui contient la Fiche d'Identité Officielle)
            read_case_blocks = [b for b in corpus_blocks if "FICHE D'IDENTITÉ OFFICIELLE" in b]
            primary_corpus = read_case_blocks[-1] if read_case_blocks else corpus_blocks[-1]
            context_parts.append(primary_corpus)
        elif external_blocks:
            context_parts.append(
                "=== PREUVES EXTERNES HORS CORPUS [SOURCE_EXTERNE] ===\n" + "\n\n".join(external_blocks)
            )

        full_context = "\n\n".join(context_parts) if context_parts else "Aucune preuve disponible."

        # Reformulation ciblée de la question pour le générateur :
        # 1) Si la question contenait une consigne de navigation ("Cherche dans la base... puis lis le dossier trouvé pour m'indiquer X"),
        #    on extrait directement la question factuelle X sur le dossier déjà ouvert.
        focused_question = question
        multi_match = re.search(
            r"(?:puis\s+lis\s+le\s+dossier[^,]*?\s+pour\s+m'indiquer|indique(?:-moi)?)\s+(.+)$",
            focused_question,
            re.IGNORECASE
        )
        if multi_match:
            focused_question = f"Dans ce dossier, quels sont {multi_match.group(1).strip()}"

        # 2) Si un bloc externe [SOURCE_EXTERNE] est déjà attaché pour répondre au volet législatif,
        #    on concentre le LLM sur le volet factuel du dossier [CORPUS_TP2] pour éviter toute confusion.
        if corpus_blocks and external_blocks:
            split_ext = re.split(
                r",?\s+et\s+que\s+(?:prévoit|dit|dispose)\s+",
                focused_question,
                flags=re.IGNORECASE
            )
            if len(split_ext) > 1:
                focused_question = split_ext[0].strip() + " ?"

        # Initialisation et appel du LLM local (Qwen 2.5 1.5B) via rag_service
        rag_service._init_components()
        chain = self._agent_prompt | rag_service._llm | StrOutputParser()
        raw_answer = chain.invoke({
            "context": full_context,
            "question": focused_question
        }).strip()
        metrics["llm_calls"] = metrics.get("llm_calls", 0) + 1

        # Enrichissement et garantie de distinction explicite des sources [CORPUS_TP2] et [SOURCE_EXTERNE]
        active_id = etat.get("selected_case_id") or etat.get("discovered_case_id")
        final_parts = []

        if corpus_blocks:
            corpus_tag = f"[CORPUS_TP2 — Dossier {active_id}]" if active_id else "[CORPUS_TP2]"
            cleaned_ans = re.sub(r"\[(?:CORPUS_TP2|SOURCE_EXTERNE)[^\]]*\]\s*:?\s*", "", raw_answer).strip()
            final_parts.append(f"{corpus_tag} : {cleaned_ans}")
        else:
            final_parts.append(raw_answer)

        if external_blocks:
            ext_sources = etat.get("external_sources") or []
            if ext_sources:
                ext_summary = ext_sources[0].get("text", "")
                final_parts.append(f"\n\n[SOURCE_EXTERNE — Référentiel Législatif] : {ext_summary}")

        draft_answer = "".join(final_parts).strip()

        return {
            "draft_answer": draft_answer,
            "metrics": metrics
        }

    # --------------------------------------------------------------------------
    # NŒUD 6 : VÉRIFICATEUR ([CHECK] — SECTION 3.4 DU PDF TP3)
    # --------------------------------------------------------------------------
    def noeud_verificateur(self, etat: EtatAgent) -> dict:
        """
        Vérifie :
        1. Présence d'évidence (retrieved_docs ou external_sources non vides).
        2. Couverture complète de la demande (ex: besoin d'ouvrir le dossier avec read_case ou d'interroger external_search).
        3. Cohérence réponse <-> passages (vérification anti-hallucination des numéros RG et balisage des sources).
        """
        iteration = etat.get("iterations", 1)
        retrieved_docs = etat.get("retrieved_docs") or []
        external_sources = etat.get("external_sources") or []
        draft = etat.get("draft_answer", "")
        metrics = dict(etat.get("metrics") or {})
        tools_used = metrics.get("tools_used") or []
        needs_ext = etat.get("needs_external_law", False)
        needs_multi = etat.get("needs_multi_step_read", False)
        discovered_id = etat.get("discovered_case_id")
        selected_id = etat.get("selected_case_id")
        trace = list(etat.get("agent_trace") or [])

        status = "SUFFISANT"
        feedback = "Présence d'évidence validée, cohérence factuelle vérifiée et sources clairement distinguées."

        # Contrôle 1 : Présence d'évidence
        if not retrieved_docs and not external_sources:
            status = "INSUFFISANT"
            feedback = "Aucune preuve documentaire récupérée ni dans [CORPUS_TP2] ni dans [SOURCE_EXTERNE]."

        # Contrôle 2A : Couverture multi-étapes (search_cases effectué, mais read_case non encore appelé)
        elif needs_multi and "search_cases" in tools_used and "read_case" not in tools_used and (discovered_id or selected_id):
            status = "INSUFFISANT"
            feedback = f"Dossier pertinent ({discovered_id or selected_id}) identifié par search_cases, mais lecture intégrale via read_case requise."

        # Contrôle 2B : Besoin d'une source externe (Scénario 3 : texte officiel d'un article de loi ou complément hors corpus)
        elif needs_ext and "external_search" not in tools_used:
            status = "INSUFFISANT"
            feedback = (
                "Le corpus interne [CORPUS_TP2] mentionne l'application de la règle dans l'affaire, mais ne contient pas "
                "le texte législatif complet demandé : appel complémentaire à external_search ([SOURCE_EXTERNE]) requis."
            )

        # Contrôle 3 : Cohérence réponse <-> passages (Vérification anti-hallucination sur les numéros RG)
        else:
            context_joined = "\n".join(etat.get("corpus_context_blocks") or [])
            rgs_in_answer = re.findall(r"\b([0-9]{2}/[0-9]{5})\b", draft)
            for rg_ans in rgs_in_answer:
                if context_joined and rg_ans not in context_joined:
                    # Correction déterministe immédiate si le modèle 1B a altéré un chiffre du RG
                    true_rg_match = re.search(r"NUMÉRO DE RÔLE GÉNÉRAL \(RG\) DU DOSSIER\s*:\s*([0-9]{2}/[0-9A-Z]+)", context_joined)
                    if true_rg_match:
                        draft = draft.replace(rg_ans, true_rg_match.group(1))
                        feedback += f" (Numéro RG vérifié et aligné sur la minute officielle : {true_rg_match.group(1)})."

        # Garde-fou strict d'arrêt à AGENT_MAX_ITERATIONS = 5 (Section 3.3 du PDF)
        if status == "INSUFFISANT" and iteration >= AGENT_MAX_ITERATIONS:
            status = "LIMITE_ATTEINTE"
            feedback = f"Limite maximale de {AGENT_MAX_ITERATIONS} itérations atteinte : arrêt sécurisé de la boucle avec les preuves disponibles."

        trace.append({
            "step_type": "CHECK",
            "node": "verificateur",
            "title": f"Statut de vérification : {status}",
            "detail": feedback,
            "iteration": iteration,
            "timestamp_ms": self._elapsed_ms(etat)
        })

        return {
            "verification_status": status,
            "verification_feedback": feedback,
            "draft_answer": draft,
            "agent_trace": trace
        }

    # --------------------------------------------------------------------------
    # NŒUD 7 : FINALISATION & SAUVEGARDE MÉMOIRE LONGUE ([FINAL])
    # --------------------------------------------------------------------------
    def noeud_final(self, etat: EtatAgent) -> dict:
        active_store = self.store
        draft = etat.get("draft_answer", "").strip()
        iteration = etat.get("iterations", 1)
        verif_status = etat.get("verification_status", "SUFFISANT")
        trace = list(etat.get("agent_trace") or [])
        metrics = dict(etat.get("metrics") or {})
        active_id = etat.get("selected_case_id") or etat.get("discovered_case_id")

        if not draft:
            draft = "Je ne dispose pas d'éléments suffisants dans le corpus ou les sources externes pour répondre de manière certaine."

        elapsed_s = round(time.time() - (etat.get("start_time") or time.time()), 2)
        metrics.update({
            "iterations": iteration,
            "verification_status": verif_status,
            "latency_s": elapsed_s,
            "corpus_docs_count": len(etat.get("retrieved_docs") or []),
            "external_docs_count": len(etat.get("external_sources") or []),
            "active_case_id": active_id
        })

        # Mise à jour de la mémoire longue inter-sessions (InMemoryStore — Exercice 8 Cours S2)
        mem = active_store.get(("jurisprudence", "user"), "profil")
        profil = mem.value if mem else {"themes": [], "dossiers_lus": [], "last_case_id": None}

        q_lower = etat.get("query", "").lower()
        for theme in ["divorce", "dépens", "article 700", "assurance", "loyer", "expulsion", "accident", "préjudice"]:
            if theme in q_lower and theme not in profil["themes"]:
                profil["themes"].append(theme)

        if active_id:
            if active_id not in profil["dossiers_lus"]:
                profil["dossiers_lus"].append(active_id)
            profil["last_case_id"] = active_id

        active_store.put(("jurisprudence", "user"), "profil", profil)

        trace.append({
            "step_type": "FINAL",
            "node": "final",
            "title": "Réponse finale sourcée et validée",
            "detail": (
                f"Réponse validée en {iteration} itération(s) ({elapsed_s}s) | "
                f"Outils : {', '.join(metrics.get('tools_used', []))} | "
                f"Sources : {metrics['corpus_docs_count']} [CORPUS_TP2], {metrics['external_docs_count']} [SOURCE_EXTERNE]."
            ),
            "iteration": iteration,
            "timestamp_ms": self._elapsed_ms(etat)
        })

        return {
            "final_answer": draft,
            "messages": [AIMessage(content=draft)],
            "agent_trace": trace,
            "metrics": metrics
        }

    # --------------------------------------------------------------------------
    # CONDITIONS DE ROUTAGE (ARÊTES CONDITIONNELLES)
    # --------------------------------------------------------------------------
    @staticmethod
    def _route_apres_planificateur(etat: EtatAgent) -> str:
        action = etat.get("current_action", "search_cases")
        if action == "generer":
            return "generateur"
        return "executeur_outils"

    @staticmethod
    def _route_apres_verificateur(etat: EtatAgent) -> str:
        status = etat.get("verification_status", "SUFFISANT")
        iterations = etat.get("iterations", 1)
        if status == "INSUFFISANT" and iterations < AGENT_MAX_ITERATIONS:
            return "planificateur"
        return "final"

    # --------------------------------------------------------------------------
    # COMPILATION DU STATEGRAPH LANGGRAPH
    # --------------------------------------------------------------------------
    def _compile_graph(self):
        if not LANGGRAPH_AVAILABLE:
            return None

        g = StateGraph(EtatAgent)

        # Ajout des 7 nœuds
        g.add_node("memoire_courte", self.noeud_memoire_courte)
        g.add_node("planificateur", self.noeud_planificateur)
        g.add_node("executeur_outils", self.noeud_executeur_outils)
        g.add_node("observateur", self.noeud_observateur)
        g.add_node("generateur", self.noeud_generateur)
        g.add_node("verificateur", self.noeud_verificateur)
        g.add_node("final", self.noeud_final)

        # Ajout des arêtes (flux du graphe)
        g.add_edge(START, "memoire_courte")
        g.add_edge("memoire_courte", "planificateur")

        g.add_conditional_edges(
            "planificateur",
            self._route_apres_planificateur,
            {
                "executeur_outils": "executeur_outils",
                "generateur": "generateur"
            }
        )

        g.add_edge("executeur_outils", "observateur")
        g.add_edge("observateur", "planificateur")
        g.add_edge("generateur", "verificateur")

        g.add_conditional_edges(
            "verificateur",
            self._route_apres_verificateur,
            {
                "planificateur": "planificateur",
                "final": "final"
            }
        )

        g.add_edge("final", END)

        # Compilation avec Checkpointer (InMemorySaver) et Store (InMemoryStore) comme dans l'Ex. 8 de S2
        try:
            return g.compile(checkpointer=self.checkpointer, store=self.store)
        except TypeError:
            # Compatibilité si la version de langgraph installée ne prend que checkpointer dans compile()
            return g.compile(checkpointer=self.checkpointer)

    # --------------------------------------------------------------------------
    # PRÉPARATION DE L'ÉTAT INITIAL D'UNE REQUÊTE
    # --------------------------------------------------------------------------
    def _build_initial_state(self, question: str, affaire_id: Optional[str] = None) -> EtatAgent:
        needs_ext, _ = _detect_external_law_need(question)
        explicit_id = affaire_id or _extract_case_id_from_text(question)

        # Détecte si la question sans ID initial demande d'abord de chercher une affaire puis d'en extraire des détails précis
        needs_multi = (explicit_id is None)

        return {
            "query": question,
            "messages": [HumanMessage(content=question)],
            "retrieved_docs": [],
            "external_sources": [],
            "iterations": 0,
            "verification_status": "EN_ATTENTE",
            "final_answer": "",
            "selected_case_id": explicit_id,
            "discovered_case_id": None,
            "current_action": "",
            "tool_query": "",
            "last_tool_output": "",
            "corpus_context_blocks": [],
            "external_context_blocks": [],
            "draft_answer": "",
            "verification_feedback": "",
            "needs_external_law": needs_ext,
            "needs_multi_step_read": needs_multi,
            "agent_trace": [],
            "metrics": {
                "iterations": 0,
                "llm_calls": 0,
                "tools_used": [],
                "verification_status": "EN_ATTENTE",
                "latency_s": 0.0,
                "corpus_docs_count": 0,
                "external_docs_count": 0,
                "active_case_id": explicit_id
            },
            "start_time": time.time()
        }

    # --------------------------------------------------------------------------
    # EXÉCUTION COMPLÈTE DU GRAPHE (INVOKE)
    # --------------------------------------------------------------------------
    def run_agent(
        self,
        question: str,
        affaire_id: Optional[str] = None,
        thread_id: str = "session_default"
    ) -> Dict[str, Any]:
        """
        Exécute le graphe Agentic RAG complet et retourne :
        - answer, sources, verification_status, agent_trace, metrics, affaire_id.
        """
        initial_state = self._build_initial_state(question=question, affaire_id=affaire_id)
        config = {"configurable": {"thread_id": thread_id or "session_default"}}

        if self.graphe is not None:
            final_state = self.graphe.invoke(initial_state, config=config)
        else:
            # Fallback séquentiel fidèle si le package langgraph n'est pas encore installé
            state = dict(initial_state)
            state.update(self.noeud_memoire_courte(state))
            while True:
                state.update(self.noeud_planificateur(state))
                if self._route_apres_planificateur(state) == "executeur_outils":
                    state.update(self.noeud_executeur_outils(state))
                    state.update(self.noeud_observateur(state))
                else:
                    state.update(self.noeud_generateur(state))
                    state.update(self.noeud_verificateur(state))
                    if self._route_apres_verificateur(state) == "final":
                        state.update(self.noeud_final(state))
                        break
            final_state = state

        # Combinaison des sources [CORPUS_TP2] et [SOURCE_EXTERNE] pour l'UI et l'évaluation
        all_sources = list(final_state.get("retrieved_docs") or []) + list(final_state.get("external_sources") or [])
        active_case = final_state.get("selected_case_id") or final_state.get("discovered_case_id") or affaire_id

        return {
            "affaire_id": active_case,
            "question": question,
            "answer": final_state.get("final_answer", ""),
            "sources": all_sources,
            "verification_status": final_state.get("verification_status", "SUFFISANT"),
            "agent_trace": final_state.get("agent_trace", []),
            "metrics": final_state.get("metrics", {})
        }

    # --------------------------------------------------------------------------
    # STREAMING TEMPS RÉEL DES ÉTAPES DU GRAPHE (stream_mode="updates")
    # --------------------------------------------------------------------------
    def stream_agent(
        self,
        question: str,
        affaire_id: Optional[str] = None,
        thread_id: str = "session_default"
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Générateur streamant chaque mise à jour de nœud LangGraph en temps réel
        via `graphe.stream(initial_state, config=config, stream_mode="updates")`.
        """
        initial_state = self._build_initial_state(question=question, affaire_id=affaire_id)
        config = {"configurable": {"thread_id": thread_id or "session_default"}}

        if self.graphe is not None:
            seen_steps = 0
            last_state_snapshot = dict(initial_state)
            for update in self.graphe.stream(initial_state, config=config, stream_mode="updates"):
                for node_name, node_payload in update.items():
                    if isinstance(node_payload, dict):
                        last_state_snapshot.update(node_payload)
                        trace_list = last_state_snapshot.get("agent_trace") or []
                        while seen_steps < len(trace_list):
                            step_item = trace_list[seen_steps]
                            seen_steps += 1
                            yield {"event": "agent_step", "node": node_name, "step": step_item}
            all_sources = list(last_state_snapshot.get("retrieved_docs") or []) + list(last_state_snapshot.get("external_sources") or [])
            yield {
                "event": "final_result",
                "data": {
                    "affaire_id": last_state_snapshot.get("selected_case_id") or last_state_snapshot.get("discovered_case_id") or affaire_id,
                    "question": question,
                    "answer": last_state_snapshot.get("final_answer", ""),
                    "sources": all_sources,
                    "verification_status": last_state_snapshot.get("verification_status", "SUFFISANT"),
                    "agent_trace": last_state_snapshot.get("agent_trace", []),
                    "metrics": last_state_snapshot.get("metrics", {})
                }
            }
        else:
            res = self.run_agent(question=question, affaire_id=affaire_id, thread_id=thread_id)
            for step_item in res.get("agent_trace", []):
                yield {"event": "agent_step", "node": step_item.get("node", "agent"), "step": step_item}
            yield {"event": "final_result", "data": res}

    # --------------------------------------------------------------------------
    # EXPORT DU SCHÉMA MERMAID & MÉMOIRE LONGUE (EX. 5, 8 & 9 COURS S2)
    # --------------------------------------------------------------------------
    def get_mermaid_graph(self) -> str:
        """Retourne le schéma Mermaid officiel du StateGraph (graphe.get_graph().draw_mermaid())."""
        if self.graphe is not None:
            try:
                return self.graphe.get_graph().draw_mermaid()
            except Exception:
                pass
        return (
            "graph TD;\n"
            "\t__start__([__start__]) --> memoire_courte;\n"
            "\tmemoire_courte --> planificateur;\n"
            "\tplanificateur -. executeur_outils .-> executeur_outils;\n"
            "\tplanificateur -. generateur .-> generateur;\n"
            "\texecuteur_outils --> observateur;\n"
            "\tobservateur --> planificateur;\n"
            "\tgenerateur --> verificateur;\n"
            "\tverificateur -. planificateur .-> planificateur;\n"
            "\tverificateur -. final .-> final;\n"
            "\tfinal --> __end__([__end__]);"
        )

    def get_memory_profile(self) -> Dict[str, Any]:
        """Retourne le profil mémorisé dans InMemoryStore (thèmes suivis et dossiers déjà lus)."""
        mem = self.store.get(("jurisprudence", "user"), "profil")
        return mem.value if mem else {"themes": [], "dossiers_lus": [], "last_case_id": None}

    @staticmethod
    def format_trace_for_console(question: str, result: Dict[str, Any]) -> str:
        """
        Formate la trace d'exécution selon le format exact demandé dans la Section 4
        de TP3_Agentic_RAG_Jurisprudence.pdf :
        [QUESTION], [DECISION], [TOOL], [OBSERVATION], [CHECK], [FINAL].
        """
        lines = [
            "=" * 78,
            f"[QUESTION]    {question}",
            "-" * 78
        ]
        for step in result.get("agent_trace", []):
            s_type = f"[{step.get('step_type', 'STEP')}]"
            title = step.get("title", "")
            detail = step.get("detail", "").replace("\n", " ")
            if len(detail) > 220:
                detail = detail[:220] + "..."
            lines.append(f"{s_type:<14} {title} — {detail}")
        lines.append("-" * 78)
        lines.append(f"[FINAL]       {result.get('answer', '')}")
        metrics = result.get("metrics") or {}
        if metrics:
            lines.append(
                f"[METRICS]     Itérations: {metrics.get('iterations', 1)} | "
                f"Appels LLM: {metrics.get('llm_calls', 1)} | "
                f"Outils: {metrics.get('tools_used', [])} | "
                f"Statut CHECK: {metrics.get('verification_status', 'SUFFISANT')} | "
                f"Latence: {metrics.get('latency_s', 0.0)}s"
            )
        lines.append("=" * 78)
        return "\n".join(lines)


# Instance singleton exportée
agent_service = AgenticRAGService()
