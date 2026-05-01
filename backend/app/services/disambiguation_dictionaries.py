"""
Disambiguation dictionaries for ambiguous location terms.

Some location words have multiple valid interpretations that depend on
the calendar event's context. For example:
  - English "bank" → financial institution OR river bank
  - German "Bank" → financial institution OR Sitzbank (park bench)

This module resolves the ambiguity by scanning the SUMMARY text for
disambiguating keywords. Each ambiguous location term has a list of
candidate concepts; each candidate has a list of trigger words. The
candidate with the most pattern hits wins. Ties or zero matches → no
disambiguation, and the standard pipeline takes over.

Each candidate may either:
  - return a concept word (looked up via the exact index), or
  - return a fixed pictogram ID (used directly).
The ID form is more robust when the desired pictogram's keyword doesn't
exactly match any single ARASAAC term you'd write down.

Patterns are matched as whole words (regex word boundaries) to avoid
false positives like "permitted" matching the trigger "mit".
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.models.schemas import Language

logger = logging.getLogger(__name__)


@dataclass
class DisambiguationCandidate:
    """
    A possible resolution of an ambiguous term, with trigger keywords.
    Either `concept` or `pictogram_id` should be set; if both are set,
    `pictogram_id` takes precedence.
    """
    concept: str | None
    patterns: list[str]
    pictogram_id: int | None = None

    def __post_init__(self):
        if self.patterns:
            escaped = "|".join(re.escape(p) for p in self.patterns)
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
                concept="river",
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
                concept="bank",   # Geldinstitut (financial)
                patterns=[
                    "termin", "geld", "kredit", "konto", "überweisung",
                    "meeting", "besprechung", "beratung", "bargeld",
                    "abheben", "einzahlen", "berater", "darlehen",
                ],
            ),
            DisambiguationCandidate(
                # Sitzbank — pinned directly to the ARASAAC park-bench
                # pictogram (id 3255) since "parkbank" is not an ARASAAC
                # keyword and the concept-based lookup would fail.
                concept=None,
                pictogram_id=3255,
                patterns=[
                    "sitzen", "ausruhen", "park", "spaziergang",
                    "picknick", "rasten", "pause", "draußen",
                    "spazieren", "rast", "natur", "wandern",
                ],
            ),
        ],
    },
}


def disambiguate_location(location: str,
                          summary_context: str,
                          language: Language) -> tuple[str | None, int | None]:
    """
    If `location` is ambiguous in the given language AND `summary_context`
    contains disambiguating keywords, return (concept, pictogram_id) for
    the winning candidate. Either may be None depending on the candidate.
    Returns (None, None) if nothing applies.
    """
    if not location:
        return (None, None)
    key = location.strip().lower()
    candidates = LOCATION_DISAMBIGUATION.get(language, {}).get(key)
    if not candidates:
        return (None, None)

    if not summary_context or not summary_context.strip():
        logger.debug(
            "[disambiguation] '%s' is ambiguous but no summary context provided.",
            key,
        )
        return (None, None)

    best: DisambiguationCandidate | None = None
    best_score = 0
    for cand in candidates:
        s = cand.score(summary_context)
        logger.debug(
            "[disambiguation] '%s' candidate '%s' scored %d",
            key, cand.concept or f"id={cand.pictogram_id}", s,
                 )
        if s > best_score:
            best_score = s
            best = cand

    if best is None or best_score == 0:
        return (None, None)

    return (best.concept, best.pictogram_id)
