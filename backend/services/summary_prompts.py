"""
backend/services/summary_prompts.py
Définition modulaire des différentes variantes de prompts pour le résumé juridique structuré (Faits, Procédure, Décision).
Conçus spécifiquement pour Llama 3.2 1B (format JSON strict, protection des accolades doubles {{...}} pour LangChain).
"""
import json
from typing import Dict, Callable
from langchain_core.prompts import ChatPromptTemplate

# ==============================================================================
# EXEMPLE GUIDÉ EN CONTEXTE (Few-Shot)
# Note : Les accolades JSON sont impérativement doublées {{...}} pour que LangChain
# ne les confonde pas avec des variables de template à interpoler.
# ==============================================================================
SHOT_USER = (
    "JURIDICTION : Tribunal judiciaire de Paris | CHAMBRE : 9e chambre\n"
    "LITIGE : M. Dupont réclame la restitution de son dépôt de garantie de 1 200 € à la SCI Immoparis.\n"
    "DÉCISION : Le tribunal condamne la SCI Immoparis à rembourser 1 200 € avec intérêts au taux légal."
)

SHOT_ASSISTANT_RAW = json.dumps({
    "faits": "M. Dupont demande à son ancien bailleur la SCI Immoparis la restitution de sa caution de 1 200 € retenue sans motif.",
    "procedure": "M. Dupont assigne la SCI devant le juge civil en restitution du dépôt de garantie et dommages-intérêts.",
    "decision": "Le tribunal condamne la SCI Immoparis à rembourser l'intégralité du dépôt de garantie de 1 200 € assorti des intérêts légaux."
}, ensure_ascii=False)

# Échappement strict {{ et }} pour la compatibilité LangChain ChatPromptTemplate
SHOT_ASSISTANT_ESCAPED = SHOT_ASSISTANT_RAW.replace("{", "{{").replace("}", "}}")


# ==============================================================================
# 1. VARIANTE FEW-SHOT JSON STANDARD (La formule éprouvée du premier benchmark)
# ==============================================================================
def get_prompt_fewshot_standard() -> ChatPromptTemplate:
    """Few-Shot standard : équilibre parfait entre concision et précision."""
    system_msg = (
        "Tu es un juriste analyste. Tu extrais les faits, la procédure et la décision "
        "sous la forme d'un objet JSON strict avec les clés : 'faits', 'procedure', 'decision'."
    )
    return ChatPromptTemplate.from_messages([
        ("system", system_msg),
        ("user", f"Décision :\n{SHOT_USER}\nJSON :"),
        ("assistant", SHOT_ASSISTANT_ESCAPED),
        ("user", "Décision :\n{texte_decision}\nJSON :")
    ])


# ==============================================================================
# 2. VARIANTE PERSONA MAGISTRAT (Fiche d'arrêt & Dispositif exécutoire)
# ==============================================================================
def get_prompt_persona_magistrat() -> ChatPromptTemplate:
    """Persona Magistrat : focalisé sur la rigueur de qualification et les condamnations."""
    system_msg = (
        "Tu es un magistrat rapporteur au Tribunal judiciaire de Paris. "
        "Rédige une fiche d'arrêt concise et rigoureuse pour l'audience. "
        "Qualifie précisément les parties (bailleur/locataire, demandeur/défendeur) "
        "et détaille les sommes ou mesures ordonnées dans 'decision'. "
        "Réponds exclusivement par un objet JSON valide avec les clés : 'faits', 'procedure', 'decision'."
    )
    return ChatPromptTemplate.from_messages([
        ("system", system_msg),
        ("user", f"Décision judiciaire :\n{SHOT_USER}\nJSON :"),
        ("assistant", SHOT_ASSISTANT_ESCAPED),
        ("user", "Décision judiciaire :\n{texte_decision}\nJSON :")
    ])


# ==============================================================================
# 3. VARIANTE CHRONOLOGIQUE (Chaîne causale des faits : Contrat -> Impayé -> Jugement)
# ==============================================================================
def get_prompt_chronologique() -> ChatPromptTemplate:
    """Chronologique : force le modèle à retracer la chronologie dans les faits."""
    system_msg = (
        "Tu es un juriste analyste méthodique. "
        "Dans 'faits' : retrace chronologiquement l'origine du litige (la relation contractuelle, l'incident ou l'impayé). "
        "Dans 'procedure' : indique qui a saisi le tribunal et quelles sont les prétentions chiffrées. "
        "Dans 'decision' : résume la solution retenue par le juge. "
        "Format obligatoire en JSON avec les clés : 'faits', 'procedure', 'decision'."
    )
    return ChatPromptTemplate.from_messages([
        ("system", system_msg),
        ("user", f"Décision :\n{SHOT_USER}\nJSON :"),
        ("assistant", SHOT_ASSISTANT_ESCAPED),
        ("user", "Décision :\n{texte_decision}\nJSON :")
    ])


# ==============================================================================
# 4. VARIANTE ZERO-SHOT JSON DIRECT (Ultra-rapide, sans exemple en amont)
# ==============================================================================
def get_prompt_zeroshot_direct() -> ChatPromptTemplate:
    """Zero-Shot direct : prompt ultra-court pour tester si le format JSON seul suffit sans exemple."""
    system_msg = (
        "Tu es un juriste analyste. Résume la décision judiciaire en un objet JSON direct "
        "avec exactement 3 clés : 'faits' (2 phrases), 'procedure' (demandes), 'decision' (dispositif). "
        "N'ajoute aucun commentaire extérieur. Format requis : "
        '{{"faits": "...", "procedure": "...", "decision": "..."}}'
    )
    return ChatPromptTemplate.from_messages([
        ("system", system_msg),
        ("user", "Décision à résumer :\n{texte_decision}\nJSON :")
    ])


# Registre central des variantes disponibles
SUMMARY_PROMPT_VARIANTS: Dict[str, Callable[[], ChatPromptTemplate]] = {
    "fewshot_standard": get_prompt_fewshot_standard,
    "magistrat": get_prompt_persona_magistrat,
    "chronologique": get_prompt_chronologique,
    "zeroshot_direct": get_prompt_zeroshot_direct,
}
