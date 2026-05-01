"""
Pre-NLP text normalizations.

Two dictionaries applied to raw input before spaCy runs:

1. ABBREVIATIONS — single-token expansions (regex-bounded by word boundaries).
   "doc" → "doctor", "appt" → "appointment", "Dr." → "doctor"
   These are intentionally narrow: only well-known shortforms that have
   a single unambiguous expansion in calendar contexts.

2. PHRASE_SYNONYMS — multi-word substitutions applied as whole-phrase
   replacements (case-insensitive). "eye doctor" → "ophthalmologist".
   These exist when the natural phrasing differs from ARASAAC's keyword.
   Use sparingly — they're not for general thesaurus mapping but for
   gluing predictable user phrasings to ARASAAC's vocabulary.

Both are applied per-language. Keys are matched case-insensitively but
replacements preserve the configured casing.
"""
from __future__ import annotations

import logging
import re

from app.models.schemas import Language

logger = logging.getLogger(__name__)


ABBREVIATIONS: dict[Language, dict[str, str]] = {
    Language.EN: {
        "doc": "doctor",
        "appt": "appointment",
        "appts": "appointments",
        "dr": "doctor",
        "dr.": "doctor",
    },
    Language.DE: {
        "dr": "doktor",
        "dr.": "doktor",
        "tel": "telefon",
        "termin": "termin",  # no-op placeholder; extend as needed
    },
}


# Multi-word phrase replacements applied BEFORE token-level expansion.
# Order matters within a language — earlier entries are tried first.
PHRASE_SYNONYMS: dict[Language, list[tuple[str, str]]] = {
    Language.EN: [
        # Multi-word verb-phrase synonyms — map common phrasings onto the
        # exact ARASAAC keyword so sliding-window finds them as one match.
        ("take a shower", "have a shower"),
        ("take shower", "have a shower"),
        ("insert hearing aid", "put on hearing aid"),
        ("put in hearing aid", "put on hearing aid"),
        # Verb-phrase normalizations (English progressive → infinitive form
        # used as ARASAAC keyword)
        ("making candle", "make candle"),
        ("making candles", "make candle"),
        ("reading tutoring", "tutoring"),
        ("choir singing", "sing"),
        # Doctor-specialty synonyms
        ("eye doctor", "ophthalmologist"),
        ("ear doctor", "otolaryngologist"),
        ("skin doctor", "dermatologist"),
        ("animal doctor", "veterinarian"),
        ("foot doctor", "podiatrist"),
        ("kids doctor", "pediatrician"),
        ("children's doctor", "pediatrician"),
        # Known cross-WordNet equivalences (when synset path can't bridge)
        ("automobile", "car"),
    ],
    Language.DE: [
        # Termin-suffix glue (for compound matching by sliding window)
        ("augenarzt termin", "augenarzttermin"),
        ("hautarzt termin", "hautarzttermin"),
        ("kinderarzt termin", "kinderarzttermin"),
        # Cross-WordNet equivalences and ARASAAC-vocabulary aliases.
        # The right-hand side must be (or be findable via) an ARASAAC keyword.
        ("automobil", "auto"),
        # Austrian regionalism — "Jause" is colloquial for snack/light meal.
        # Also expand the compound form to bypass splitting.
        ("nachmittagsjause", "nachmittag snack"),
        ("nachmittag jause", "nachmittag snack"),
        ("jause", "snack"),
        # Specialist titles WordNet's German index does not cover —
        # bypass splitting and synset traversal by mapping directly.
        ("kieferorthopäde", "zahnarzt"),
        ("kieferchirurg", "zahnarzt"),
        ("orthodontie", "zahnarzt"),
        # Compound nouns whose constituents aren't both ARASAAC keywords
        # (so the splitter rejects them) but whose meaning resolves cleanly.
        ("schwimmstunde", "schwimmen unterricht"),
        ("schwimmkurs", "schwimmen unterricht"),
        # Medical/admin vocabulary not in ARASAAC's German keywords.
        ("verschreibung", "rezept"),
        ("rezept abholen", "rezept abholen"),  # placeholder if you want this exact phrase
    ],
}


def normalize(text: str, language: Language) -> str:
    """
    Apply phrase synonyms first, then word-boundary token expansions.
    Returns the normalized text, lowercased only for matching purposes —
    the original casing of non-replaced words is preserved.
    """
    if not text or not text.strip():
        return text

    result = text

    # Tier 1: phrase-level synonyms (longest-first within configured order)
    for phrase, replacement in PHRASE_SYNONYMS.get(language, []):
        pattern = re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)
        if pattern.search(result):
            new_result = pattern.sub(replacement, result)
            if new_result != result:
                logger.info("[normalize] phrase '%s' → '%s'", phrase, replacement)
                result = new_result

    # Tier 2: token abbreviations
    abbrevs = ABBREVIATIONS.get(language, {})
    if abbrevs:
        # Build a single regex that matches any abbreviation as a whole word
        # (allowing optional trailing period for entries like 'dr.')
        keys_with_dot = sorted(
            (k for k in abbrevs if k.endswith(".")),
            key=len, reverse=True,
        )
        keys_plain = sorted(
            (k for k in abbrevs if not k.endswith(".")),
            key=len, reverse=True,
        )

        # Process dotted keys first (so "dr." is matched before "dr")
        for k in keys_with_dot:
            replacement = abbrevs[k]
            pattern = re.compile(
                rf"(?<!\w){re.escape(k)}(?!\w)", re.IGNORECASE
            )
            if pattern.search(result):
                logger.info("[normalize] abbrev '%s' → '%s'", k, replacement)
                result = pattern.sub(replacement, result)

        for k in keys_plain:
            replacement = abbrevs[k]
            # Word-boundary match without consuming a trailing period if any
            pattern = re.compile(rf"\b{re.escape(k)}\b", re.IGNORECASE)
            if pattern.search(result):
                logger.info("[normalize] abbrev '%s' → '%s'", k, replacement)
                result = pattern.sub(replacement, result)

    return result
