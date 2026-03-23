"""
pipeline/nlp.py

Neighborhood (bairro) extraction for Aracaju/SE.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Complete list of Aracaju neighborhoods
BAIRROS_ARACAJU = [
    "Atalaia",
    "Centro",
    "Coroa do Meio",
    "Farolândia",
    "Jardins",
    "São Conrado",
    "Luzia",
    "Grageru",
    "Industrial",
    "Jabotiana",
    "Bugio",
    "Cirurgia",
    "13 de Julho",
    "Siqueira Campos",
    "Getúlio Vargas",
    "Suíssa",
    "Santo Antônio",
    "Palestina",
    "América",
    "Zona de Expansão",
    "Novo Paraíso",
    "Porto Dantas",
    "Lamarão",
    "Soledade",
    "São José",
    "Pereira Lobo",
    "Capucho",
    "Cidade Nova",
    "Aeroporto",
    "Ponto Novo",
]

# Compile case-insensitive patterns for each neighborhood (longest first to avoid partial matches)
_BAIRRO_PATTERNS = [
    (bairro, re.compile(r"\b" + re.escape(bairro) + r"\b", re.IGNORECASE))
    for bairro in sorted(BAIRROS_ARACAJU, key=len, reverse=True)
]

# Attempt to load spaCy once at module level
_nlp = None
_SPACY_AVAILABLE = False

try:
    import spacy  # type: ignore

    try:
        _nlp = spacy.load("pt_core_news_sm")
        _SPACY_AVAILABLE = True
        logger.debug("spaCy model pt_core_news_sm loaded successfully.")
    except OSError:
        logger.warning(
            "spaCy model 'pt_core_news_sm' not found. "
            "Run: python -m spacy download pt_core_news_sm"
        )
except ImportError:
    logger.warning("spaCy not installed. Neighborhood extraction will use exact match only.")


def _exact_match(text: str) -> Optional[str]:
    """Return first bairro found via exact (case-insensitive, word-boundary) match."""
    for bairro, pattern in _BAIRRO_PATTERNS:
        if pattern.search(text):
            return bairro
    return None


def _spacy_match(text: str) -> Optional[str]:
    """
    Use spaCy NER to find LOC entities, then check if any entity text
    matches a known bairro (threshold: entity confidence >= 0.7 when available).
    """
    if not _SPACY_AVAILABLE or _nlp is None:
        return None

    doc = _nlp(text)
    for ent in doc.ents:
        if ent.label_ not in ("LOC", "GPE"):
            continue
        # spaCy v3 does not expose per-entity scores directly in default pipeline;
        # we use the entity text to attempt an exact match against the bairro list.
        candidate = _exact_match(ent.text)
        if candidate:
            return candidate
    return None


def extract_bairro(text: str) -> Optional[str]:
    """
    Extract neighborhood name from text.

    Strategy:
    1. Exact case-insensitive word-boundary match against BAIRROS_ARACAJU list.
    2. Fallback: spaCy NER LOC/GPE entities matched against the list.
    3. Returns None if no match found.
    """
    if not text:
        return None

    result = _exact_match(text)
    if result:
        return result

    result = _spacy_match(text)
    return result
