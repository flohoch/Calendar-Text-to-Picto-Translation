"""
Disambiguation dictionaries for ambiguous location terms.

Some location words have multiple valid interpretations that depend on
the calendar event's context. For example:
  - English "bank" → financial institution OR river bank
  - German "Bank" → financial institution OR park bench (Sitzbank)

This module resolves the ambiguity by scanning the SUMMARY text for
disambiguating keywords. Each ambiguous location term has a list of
candidate concepts; each candidate has a list of trigger words. The
candidate with the most pattern hits wins. Ties or zero matches → no
disambiguation, and the standard pipeline takes over.

Patterns are matched as whole words (regex word boundaries) to avoid
false positives like "permitted" matching the trigger "mit".
"""
from __future__ import annotations

import logging
import re

from app.models.schemas import Language

logger = logging.getLogger(__name__)


class DisambiguationCandidate:
    """A possible resolution of an ambiguous term, with trigger keywords."""

    def __init__(self, concept: str, patterns: list[str]):
        self.concept = concept
        self.patterns = patterns
        if patterns:
            escaped = "|".join(re.escape(p) for p in patterns)
            self._regex = re.compile(rf"\b({escaped})\b", re.IGNORECASE)
        else:
            self._regex = None

    def score(self, context: str) -> int:
        """Return the number of pattern hits in `context`."""
        if not self._regex or not context:
            return 0
        return len(self._regex.findall(context))


# Per-language disambiguation tables.
# Keys are the lowercased ambiguous location terms; values list candidate
# concepts in priority order (used as tiebreaker when scores are equal).
LOCATION_DISAMBIGUATION: dict[Language, dict[str, list[DisambiguationCandidate]]] = {
    Language.EN: {
        "bank": [
            DisambiguationCandidate(
                concept="bank",   # financial institution
                patterns=[
                    "meeting", "money", "loan", "deposit", "account",
                    "withdraw", "atm", "cash", "appointment", "transfer",
                    "check", "cheque", "savings", "mortgage", "advisor",
                ],
            ),
            DisambiguationCandidate(
                concept="river",   # river bank
                patterns=[
                    "picnic", "river", "lake", "fishing", "walk",
                    "nature", "outdoor", "swim", "kayak", "stroll",
                    "boat", "fish",
                ],
            ),
        ],
    },
    Language.DE: {
        "bank": [
            DisambiguationCandidate(
                concept="bank",   # Geldinstitut
                patterns=[
                    "termin", "geld", "kredit", "konto", "überweisung",
                    "meeting", "besprechung", "beratung", "bargeld",
                    "abheben", "einzahlen", "berater", "darlehen",
                ],
            ),
            DisambiguationCandidate(
                concept="park",   # Sitzbank → fall back to "park" pictogram
                patterns=[
                    "sitzen", "ausruhen", "park", "spaziergang",
                    "picknick", "rasten", "pause", "draußen",
                    "spazieren", "rast",
                ],
            ),
        ],
    },
}


def disambiguate_location(location: str,
                          summary_context: str,
                          language: Language) -> str | None:
    """
    If `location` is ambiguous in the given language AND `summary_context`
    contains disambiguating keywords, return the resolved concept word.
    Returns None if there is no ambiguity entry, or if no candidate scores
    higher than zero.
    """
    if not location:
        return None
    key = location.strip().lower()
    candidates = LOCATION_DISAMBIGUATION.get(language, {}).get(key)
    if not candidates:
        return None

    if not summary_context or not summary_context.strip():
        # Ambiguous term but no context — refuse to guess.
        logger.debug("[disambiguation] '%s' is ambiguous but no summary context provided.", key)
        return None

    best_concept: str | None = None
    best_score = 0
    for cand in candidates:
        s = cand.score(summary_context)
        logger.debug("[disambiguation] '%s' candidate '%s' scored %d", key, cand.concept, s)
        if s > best_score:
            best_score = s
            best_concept = cand.concept

    if best_score == 0:
        return None

    return best_concept
