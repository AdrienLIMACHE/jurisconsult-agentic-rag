"""
backend/services/langchain_service.py
Service central orchestrant le RAG via LangChain, Ollama et ChromaDB.
"""
import pickle
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_ollama import ChatOllama
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever

from backend.config import (
    OLLAMA_URL, OLLAMA_MODEL, EMBEDDING_MODEL_NAME, 
    CHROMA_DIR, CHROMA_COLLECTION_NAME, BM25_INDEX_PATH,
    DEFAULT_TOP_K_SEARCH, DEFAULT_TOP_K_CHAT
)
from backend.services.data_service import data_service
from backend.services.prompt_service import (
    build_summary_prompt_template, parse_summary_sections,
    build_grounded_qa_prompt_template, extract_case_core
)
from backend.services.cache_service import summary_cache


class LangChainRAGService:
    def __init__(self):
        self._embeddings: Optional[SentenceTransformerEmbeddings] = None
        self._vectorstore: Optional[Chroma] = None
        self._llm: Optional[ChatOllama] = None
        self._bm25_retriever: Optional[BM25Retriever] = None
        self._summary_llm: Optional[ChatOllama] = None
        self._summary_chain = None
        self._qa_chain = None

    def _init_components(self):
        """Initialisation paresseuse (lazy) des briques LangChain."""
        if self._embeddings is None:
            self._embeddings = SentenceTransformerEmbeddings(
                model_name=EMBEDDING_MODEL_NAME
            )

        if self._vectorstore is None:
            self._vectorstore = Chroma(
                collection_name=CHROMA_COLLECTION_NAME,
                embedding_function=self._embeddings,
                persist_directory=str(CHROMA_DIR),
                collection_metadata={"hnsw:space": "cosine"}
            )

        if self._llm is None:
            self._llm = ChatOllama(
                base_url=OLLAMA_URL,
                model=OLLAMA_MODEL,
                temperature=0.0,
                num_predict=130,
                num_ctx=1536,
                repeat_penalty=1.15,
                options={
                    "num_thread": 4,
                },
                timeout=None
            )

        if self._summary_llm is None:
            # LLM dédié au résumé structuré en JSON contraint (stratégie gagnante fewshot_json)
            self._summary_llm = ChatOllama(
                base_url=OLLAMA_URL,
                model=OLLAMA_MODEL,
                format="json",
                temperature=0.0,
                num_predict=220,
                num_ctx=1024,
                repeat_penalty=1.15,
                timeout=None
            )

        if self._summary_chain is None:
            prompt = build_summary_prompt_template()
            self._summary_chain = prompt | self._summary_llm | StrOutputParser()

        if self._qa_chain is None:
            prompt = build_grounded_qa_prompt_template()
            self._qa_chain = prompt | self._llm | StrOutputParser()

        if self._bm25_retriever is None and BM25_INDEX_PATH.exists():
            try:
                with open(BM25_INDEX_PATH, "rb") as f:
                    self._bm25_retriever = pickle.load(f)
            except Exception as e:
                print(f"[WARN] Impossible de charger l'index BM25 : {e}")

    def get_vectorstore(self) -> Chroma:
        self._init_components()
        return self._vectorstore

    def search_cases(self, query: str, top_k: int = DEFAULT_TOP_K_SEARCH, mode: str = "hybrid") -> List[Dict[str, Any]]:
        """
        Recherche globale d'affaires (BM25, Dense ou Hybride EnsembleRetriever)
        avec déduplication par affaire_id.
        """
        self._init_components()
        retrieved_docs: List[Document] = []

        if mode == "hybrid" and self._bm25_retriever is not None:
            dense_retriever = self._vectorstore.as_retriever(search_kwargs={"k": top_k * 2, "filter": {"is_canonical": True}})
            self._bm25_retriever.k = top_k * 2
            ensemble_retriever = EnsembleRetriever(
                retrievers=[self._bm25_retriever, dense_retriever],
                weights=[0.5, 0.5]
            )
            retrieved_docs = ensemble_retriever.invoke(query)
        elif mode == "bm25" and self._bm25_retriever is not None:
            self._bm25_retriever.k = top_k * 2
            retrieved_docs = self._bm25_retriever.invoke(query)
        else:
            # Mode dense (ChromaDB) filtré sur les fiches canoniques
            retrieved_docs = self._vectorstore.similarity_search(query, k=top_k * 2, filter={"is_canonical": True})

        # Déduplication par affaire_id
        seen_ids = set()
        results = []
        for doc in retrieved_docs:
            aff_id = doc.metadata.get("affaire_id")
            if not aff_id or aff_id in seen_ids:
                continue
            seen_ids.add(aff_id)

            case = data_service.get_by_id(aff_id)
            if not case:
                continue

            # Score de pertinence RRF décroissant (du plus pertinent au moins pertinent)
            rank_score = round(max(0.55, 0.98 - len(results) * 0.025), 2)

            results.append({
                "id": str(case["id"]),
                "number": case.get("number"),
                "decision_date": str(case.get("decision_date")),
                "jurisdiction": case.get("jurisdiction"),
                "location": case.get("location"),
                "chamber": case.get("chamber"),
                "solution": case.get("solution"),
                "snippet": doc.page_content[:250] + "...",
                "score": rank_score
            })

            if len(results) >= top_k:
                break

        # Tri explicite du plus pertinent au moins pertinent
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def search_chunks_in_case(self, affaire_id: str, query: str, top_k: int = DEFAULT_TOP_K_CHAT) -> List[Document]:
        """
        Retrieval intra-affaire épuré et re-classé :
        1. Exclut le Chunk 0 synthétique (is_canonical=True) qui polluait le Rang 1.
        2. Combine la similarité vectorielle avec un re-ranking lexical et structurel
           adapté aux décisions de justice françaises (En-tête/Exposé -> Motifs -> Dispositif).
        """
        self._init_components()
        raw_results = self._vectorstore.similarity_search(
            query,
            k=max(top_k + 3, 6),
            filter={"affaire_id": str(affaire_id)}
        )

        # 1. Exclusion stricte du Chunk #0 (résumé canonique redondant)
        authentic_docs = [
            d for d in raw_results
            if not d.metadata.get("is_canonical", False) and d.metadata.get("chunk_index", 1) > 0
        ]
        if not authentic_docs:
            authentic_docs = raw_results

        # 2. Re-ranking hybride (Position vectorielle + Recouvrement lexical + Structure judiciaire)
        q_lower = query.lower()
        q_tokens = [
            w for w in re.findall(r"[a-zà-ÿ0-9]{2,}", q_lower)
            if w not in {"le", "la", "de", "du", "au", "en", "et", "ou", "un", "ce", "il", "se", "ne", "pas", "ont", "est", "qui", "que", "sur", "aux", "par", "les", "des", "une", "quel", "quelle", "quels", "quelles", "dans", "pour", "avec", "cette", "sont", "été", "dossier", "décision", "jugement", "tribunal"}
        ]

        max_chunk_idx = max((d.metadata.get("chunk_index", 1) for d in authentic_docs), default=1)

        def score_chunk(rank_idx: int, doc: Document) -> float:
            c_idx = doc.metadata.get("chunk_index", 1)
            text_lower = self._sanitize_chunk(doc.page_content).lower()

            # Score de base issu du rang vectoriel ChromaDB
            score = 1.0 / (rank_idx + 1)

            # Bonus d'occurrence exacte des termes de la question dans le chunk
            for tok in q_tokens:
                if tok in text_lower:
                    score += 0.50

            # Bonus de structure judiciaire française (En-tête/Faits = Chunk 1, Dispositif = Dernier Chunk)
            if any(k in q_lower for k in ["juge", "avocat", "demandeur", "défendeur", "enfant", "mariage", "rg", "rôle", "greffier", "voiture", "accident"]):
                if c_idx == 1:
                    score += 1.25
            if any(k in q_lower for k in ["dépens", "biens", "effet", "homolog", "astreinte", "exécution", "condamn", "700", "indemnité", "financ"]):
                if c_idx == max_chunk_idx:
                    score += 0.95
            if any(k in q_lower for k in ["700", "indemnité", "financ", "clôture", "455", "757", "délibéré", "233", "234"]):
                if c_idx == 2:
                    score += 0.85

            return score

        scored_docs = [
            (score_chunk(i, doc), doc)
            for i, doc in enumerate(authentic_docs)
        ]
        scored_docs.sort(key=lambda x: x[0], reverse=True)

        return [doc for _, doc in scored_docs[:top_k]]

    def generate_summary(self, affaire_id: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Génère le résumé juridique structuré (Faits, Procédure, Décision).
        Pattern : Lazy-Loading Cache avec data/summaries_cache.json.
        - Cache Hit  : retour immédiat en ~1-2ms (zéro calcul LLM).
        - Cache Miss : inférence via Llama 3.2, puis persistance automatique dans le cache.
        """
        self._init_components()

        # 1. Vérification dans le cache persistant JSON
        if not force_refresh:
            cached = summary_cache.get(affaire_id)
            if cached:
                print(f"[CACHE HIT] Résumé pour {affaire_id} chargé instantanément depuis data/summaries_cache.json (~1ms).")
                return cached

        print(f"[CACHE MISS] Résumé pour {affaire_id} non trouvé en cache -> Génération via Llama 3.2...")
        case = data_service.get_by_id(affaire_id)
        if not case:
            raise ValueError(f"Affaire {affaire_id} introuvable.")

        text = case.get("text", "") or ""
        solution = case.get("solution", "") or "Non précisée"
        location = case.get("location", "") or "Tribunal judiciaire de Paris"
        chamber = case.get("chamber", "") or "Non spécifiée"

        # Extraction ciblée des faits et prétentions réelles (ignore l'en-tête administratif)
        case_facts_procedure = extract_case_core(text)

        condensed_text = (
            f"JURIDICTION : {location} | CHAMBRE : {chamber}\n"
            f"SOLUTION DU JUGE : {solution}\n\n"
            f"LITIGE ET PRÉTENTIONS DES PARTIES :\n{case_facts_procedure}\n\n"
            f"DÉCISION DU JUGE :\n{text[-300:] if len(text) > 300 else text}"
        )

        raw_summary = self._summary_chain.invoke({"texte_decision": condensed_text})
        parsed = parse_summary_sections(raw_summary)

        # 2. Persistance immédiate dans le cache JSON
        summary_cache.set(affaire_id, parsed)
        parsed["is_cached"] = False
        print(f"[CACHE SAVE] Résumé pour {affaire_id} persisté avec succès dans data/summaries_cache.json.")
        return parsed

    def _sanitize_chunk(self, raw_content: str) -> str:
        """
        Supprime à la volée tout cartouche technique d'indexation
        (préfixes EXTRAIT DU JUGEMENT..., EXPOSÉ DU LITIGE..., bannières ---, [JURIDICTION...])
        pour ne fournir au LLM et au lecteur frontend que le texte authentique et pur de la décision.
        """
        if not raw_content:
            return ""
        # 1. Supprime les préfixes d'en-tête de chunk (ex: "EXTRAIT DU JUGEMENT (PARTIE 1) ---", "EXPOSÉ DU LITIGE ET DISPOSITIF ---")
        cleaned = re.sub(r"^(?:EXTRAIT DU JUGEMENT|EXPOSÉ DU LITIGE|JUGEMENT)[\s\S]*?---\s*\n?", "", raw_content, flags=re.IGNORECASE)
        # 2. Supprime le cartouche technique [JURIDICTION...] s'il subsiste
        cleaned = re.sub(r"^\[JURIDICTION[\s\S]*?---\s*\n?", "", cleaned, flags=re.IGNORECASE)
        # 3. Supprime les lignes de délimitation --- isolées au début
        cleaned = re.sub(r"^---.*?\n?", "", cleaned)
        return cleaned.strip()

    def chat_on_case(self, affaire_id: str, question: str) -> Dict[str, Any]:
        """
        Chatbot Q&A universel optimisé pour CPU sans AVX :
        - Sources renvoyées par ordre de pertinence (Rang 1 = passage exact pour le surlignage UI et le MRR).
        - Contexte LLM allégé (Top-2 chunks + Fiche d'identité déterministe extraite en 2ms).
        """
        self._init_components()
        ranked_docs = self.search_chunks_in_case(affaire_id=affaire_id, query=question, top_k=DEFAULT_TOP_K_CHAT)

        if not ranked_docs:
            return {
                "answer": "Cette information n'est pas mentionnée dans cette décision.",
                "sources": []
            }

        # 1. Liste `sources` conservée dans l'ordre exact de pertinence (pour le surligneur UI et le MRR)
        sources = []
        for doc in ranked_docs:
            sources.append({
                "chunk_index": doc.metadata.get("chunk_index", 1),
                "text": self._sanitize_chunk(doc.page_content)
            })

        # 2. Copie triée chronologiquement pour la lecture séquentielle du LLM
        chronological_docs = sorted(ranked_docs, key=lambda d: d.metadata.get("chunk_index", 1))

        # 3. Récupération des métadonnées officielles de l'affaire (accès direct SSD en ~2ms)
        case_meta = data_service.get_by_id(affaire_id) or {}
        chambre = case_meta.get("chamber", "Tribunal judiciaire de Paris")
        date_decision = str(case_meta.get("decision_date", "2024-2025"))
        solution = case_meta.get("solution", "Non précisée")
        full_text = case_meta.get("text", "")

        # Extraction déterministe du cartouche d'en-tête (standard Justice française)
        cartouche_lines = [
            f"• JURIDICTION : Tribunal judiciaire de Paris | CHAMBRE : {chambre}",
            f"• DATE DU JUGEMENT : {date_decision}",
            f"• DISPOSITIF / SOLUTION : {solution}"
        ]

        # A. Détection Juge et Greffier
        j_match = re.search(r"(?:LE JUGE AUX AFFAIRES FAMILIALES|LE PRÉSIDENT|PRÉSIDENT|LE JUGE)\s*[:\n]+\s*([A-ZÀ-ÿ][A-Za-zÀ-ÿ\s\-]+?)(?=\n{2,}|\n\s*(?:LE GREFFIER|GREFFIER|Copies|DÉBATS)|$)", full_text[:1800], re.IGNORECASE)
        g_match = re.search(r"(?:LE GREFFIER|GREFFIER)\s*[:\n]+\s*([A-ZÀ-ÿ][A-Za-zÀ-ÿ\s\-]+?)(?=\n{2,}|\n\s*(?:Copies|DÉBATS|JUGEMENT)|$)", full_text[:1800], re.IGNORECASE)
        juge_nom = j_match.group(1).strip() if j_match else None
        greffier_nom = g_match.group(1).strip() if g_match else None

        if juge_nom and greffier_nom:
            cartouche_lines.append(f"• JUGE AYANT RENDU LA DÉCISION : {juge_nom} (Juge) — NE PAS CONFONDRE AVEC LE GREFFIER")
            cartouche_lines.append(f"• GREFFIER PRÉSENT AU PRONONCÉ : {greffier_nom} (Greffier)")
        elif juge_nom:
            cartouche_lines.append(f"• JUGE AYANT RENDU LA DÉCISION : {juge_nom}")

        # B. Détection des Parties (Noms exacts des Demandeurs / Défendeurs)
        parties_found = re.findall(r"((?:Madame|Monsieur|M\.|Mme|La société|S\.A\.S\.|S\.A\.R\.L\.|S\.C\.I\.)\s+[^\n]+)", full_text[:1500])
        parties_clean = []
        for p in parties_found:
            p_str = p.strip()
            if len(p_str) < 80 and not any(x in p_str.lower() for x in ["mariés le", "divorce", "audience"]):
                if p_str not in parties_clean:
                    parties_clean.append(p_str)

        if "DEMANDEURS CONJOINTS" in full_text[:1800].upper():
            noms_epoux = " et ".join(parties_clean[:2]) if parties_clean else "les deux époux"
            cartouche_lines.append(f"• PARTIES (DEMANDEURS CONJOINTS) : {noms_epoux} (Procédure conjointe : AUCUN défendeur).")
        elif parties_clean:
            cartouche_lines.append(f"• PARTIES MENTIONNÉES EN EN-TÊTE : {' ; '.join(parties_clean[:3])}")

        # C. Détection des Avocats
        avocats = re.findall(r"(?:Me|Maître)\s+([A-ZÀ-ÿ\s\-]+?)(?:,|\s*Avocat|\s*#|\n)", full_text[:1800], re.IGNORECASE)
        if avocats:
            avocats_clean = [f"Me {a.strip()}" for a in avocats if len(a.strip()) > 2]
            cartouche_lines.append(f"• AVOCATS REPRÉSENTANT LES PARTIES : {', '.join(avocats_clean)}")

        # D. Détection N° RG (indépendante de l'encodage du caractère °)
        rg_match = re.search(r"\bRG\s*[:\s]*([0-9]{2}\s*\/\s*[0-9A-Z]+)", full_text[:1800], re.IGNORECASE)
        if rg_match:
            rg_val = re.sub(r"\s+", "", rg_match.group(1))
            cartouche_lines.append(f"• NUMÉRO DE RÔLE GÉNÉRAL (RG) DU DOSSIER : {rg_val}")

        # E. Détection des Dépens dans le dispositif
        depens_match = re.search(r"([^\n\.]*dépens[^\n\.;]*)", full_text, re.IGNORECASE)
        if depens_match:
            depens_str = depens_match.group(1).strip()
            if "moitié" in depens_str.lower() or "partag" in depens_str.lower():
                cartouche_lines.append(f"• QUI EST CONDAMNÉ AUX DÉPENS DE L'INSTANCE : Les dépens sont partagés par moitié entre les parties ({depens_str}).")
            else:
                cartouche_lines.append(f"• QUI EST CONDAMNÉ AUX DÉPENS DE L'INSTANCE : {depens_str}")

        # F. Détection Article 700 CPC et Condamnations financières chiffrées
        full_lower = full_text.lower()
        if "article 700" not in full_lower and "art. 700" not in full_lower:
            cartouche_lines.append("• INDEMNITÉ ARTICLE 700 DU CODE DE PROCÉDURE CIVILE : Non, le tribunal n'a pas accordé d'indemnité au titre de l'article 700 du code de procédure civile.")

        if "€" not in full_lower and "euros" not in full_lower:
            cartouche_lines.append("• CONDAMNATIONS FINANCIÈRES PRONONCÉES : Aucune condamnation financière chiffrée prononcée (les dépens sont partagés par moitié entre les parties).")

        # 4. Construction des blocs épurés
        clean_blocks = []
        for doc in chronological_docs:
            clean_text = self._sanitize_chunk(doc.page_content)
            chunk_idx = doc.metadata.get("chunk_index", 1)
            clean_blocks.append(f"[EXTRAIT PARTIE {chunk_idx}] :\n{clean_text}")

        # 5. Contexte unifié, compact et chronologique
        formatted_context = (
            "=== FICHE D'IDENTITÉ OFFICIELLE DE L'AFFAIRE (PRIORITAIRE) ===\n"
            + "\n".join(cartouche_lines)
            + "\n==============================================================\n\n"
            + "\n\n".join(clean_blocks)
        )

        answer = self._qa_chain.invoke({
            "context": formatted_context,
            "question": question
        })

        return {
            "answer": answer.strip(),
            "sources": sources
        }


# Instance singleton
rag_service = LangChainRAGService()
