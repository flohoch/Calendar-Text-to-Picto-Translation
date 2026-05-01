"""
Shared matching pipeline. Used by summary/location/attendee services.

Tier order (within a single field):
  1. SLIDING_WINDOW (longest multi-word phrase first)
  2. EXACT keyword match (single token)
  3. LEMMA lookup
  4. SYNSET lookup (ARASAAC-WN)
  5. HYPERNYM traversal (1-2 levels)
  6. (Generic fallback handled by caller — depends on category)

Sliding window runs first because the longer phrase is the more specific
intent. "Zähne putzen" should match the brushing-teeth pictogram before
"Zähne" matches a generic teeth pictogram.

For ambiguous keywords (e.g. "bathroom" matches several pictograms),
results are sorted by ARASAAC download count at index-build time, so
the most-used pictogram comes first by default. A separate
preferred_pictograms.py override lets us hardcode the preferred ID for
specific terms when the download heuristic isn't enough.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.models.schemas import (Language, MatchType, Pictogram, PictogramMatch)
from app.services import index_service, preferred_pictograms, synset_service

logger = logging.getLogger(__name__)

HYPERNYM_MAX_DEPTH = 2


@dataclass
class MatchAttempt:
    pictogram: Pictogram | None = None
    match_type: MatchType | None = None
    confidence_override: float | None = None
    matched_term: str | None = None


def _select_preferred(results: list[Pictogram],
                      term: str,
                      language: Language) -> Pictogram:
    """
    Given a non-empty list of candidate pictograms for `term`, return the
    preferred one — either the explicitly-overridden ID, or the first
    result (which is already the most-downloaded due to index sorting).
    """
    preferred_id = preferred_pictograms.get_preferred(term, language)
    if preferred_id is not None:
        for p in results:
            if p.id == preferred_id:
                return p
    return results[0]


def find_for_phrase(phrase: str, language: Language) -> MatchAttempt:
    """Tier 2 — single-token exact match (also used as the lookup primitive)."""
    results = index_service.find_by_exact(phrase, language)
    if results:
        chosen = _select_preferred(results, phrase, language)
        return MatchAttempt(
            pictogram=chosen,
            match_type=MatchType.EXACT,
            matched_term=phrase,
        )
    return MatchAttempt()


def find_sliding_window(tokens: list[str], start: int,
                        language: Language) -> tuple[MatchAttempt, int]:
    """
    Tier 1 — try the longest possible phrase starting at `start`, shrinking
    until a match. Returns (match, consumed_count). consumed_count > 1 only
    for genuine multi-word matches; single-token windows return consumed=0.
    """
    n = len(tokens)
    for window_size in range(n - start, 1, -1):
        phrase = " ".join(tokens[start : start + window_size])
        results = index_service.find_by_exact(phrase, language)
        if results:
            chosen = _select_preferred(results, phrase, language)
            return (
                MatchAttempt(
                    pictogram=chosen,
                    match_type=MatchType.SLIDING_WINDOW,
                    matched_term=phrase,
                ),
                window_size,
            )
    return MatchAttempt(), 0


def find_for_lemma(lemma: str, language: Language) -> MatchAttempt:
    """Tier 3 — lemma lookup."""
    results = index_service.find_by_lemma(lemma, language)
    if results:
        chosen = _select_preferred(results, lemma, language)
        return MatchAttempt(
            pictogram=chosen,
            match_type=MatchType.LEMMA,
            matched_term=lemma,
        )
    return MatchAttempt()


def _candidate_synsets(token: str, lemma: str, language: Language) -> set[str]:
    """
    Collect candidate synsets for a token/lemma. First tries the
    keyword-to-synsets map (built from ARASAAC keyword tagging). If that
    yields nothing, falls back to a direct WordNet lookup on the lemma —
    this handles words like 'orthodontist' that aren't ARASAAC keywords
    but still exist in WordNet with relevant hypernyms.
    """
    candidates: set[str] = set()
    candidates.update(index_service.get_synsets_for_keyword(token, language))
    if lemma != token:
        candidates.update(index_service.get_synsets_for_keyword(lemma, language))

    if candidates:
        return candidates

    # Direct WordNet fallback (English-only). For German, this only helps
    # if the lemma happens to coincide with an English word.
    candidates.update(synset_service.lookup_synsets_for_word(lemma))
    if lemma != token:
        candidates.update(synset_service.lookup_synsets_for_word(token))
    return candidates


def find_via_synset(token: str, lemma: str, language: Language) -> MatchAttempt:
    """Tier 4 — direct synset match."""
    candidate_synsets = _candidate_synsets(token, lemma, language)
    if not candidate_synsets:
        return MatchAttempt()

    direct = index_service.find_by_any_synset(candidate_synsets, language)
    if direct:
        return MatchAttempt(
            pictogram=direct[0],
            match_type=MatchType.SYNSET,
            matched_term=lemma,
        )
    return MatchAttempt()


def find_via_hypernym(token: str, lemma: str, language: Language,
                      max_depth: int = HYPERNYM_MAX_DEPTH) -> MatchAttempt:
    """Tier 5 — hypernym traversal up to max_depth levels."""
    if not synset_service.is_available():
        return MatchAttempt()

    candidate_synsets = _candidate_synsets(token, lemma, language)
    if not candidate_synsets:
        return MatchAttempt()

    hypernym_levels = synset_service.get_hypernyms_for_all(
        candidate_synsets, max_depth=max_depth
    )
    for level_idx, level_ids in enumerate(hypernym_levels):
        matches = index_service.find_by_any_synset(level_ids, language)
        if matches:
            confidence = 0.55 - (0.1 * level_idx)
            return MatchAttempt(
                pictogram=matches[0],
                match_type=MatchType.HYPERNYM,
                confidence_override=max(0.3, confidence),
                matched_term=f"{lemma} (hypernym L{level_idx + 1})",
            )
    return MatchAttempt()


def run_full_pipeline(token: str, lemma: str, language: Language,
                      original_input: str) -> PictogramMatch | None:
    """
    Run tiers 2, 3, 4, 5 for a single token. Sliding window (tier 1)
    is invoked separately by callers that operate on multi-token sequences.
    Returns the first successful match, or None.
    """
    # Tier 2: Exact
    attempt = find_for_phrase(token, language)
    if attempt.pictogram:
        logger.debug("  EXACT: '%s' → %d", token, attempt.pictogram.id)
        return attempt.pictogram.to_match(
            original_input, attempt.matched_term or token, attempt.match_type
        )

    # Tier 3: Lemma
    if lemma != token:
        attempt = find_for_lemma(lemma, language)
        if attempt.pictogram:
            logger.debug("  LEMMA: '%s'→'%s' → %d", token, lemma, attempt.pictogram.id)
            return attempt.pictogram.to_match(
                original_input, attempt.matched_term or lemma, attempt.match_type
            )
    else:
        attempt = find_for_lemma(token, language)
        if attempt.pictogram:
            logger.debug("  LEMMA: '%s' → %d", token, attempt.pictogram.id)
            return attempt.pictogram.to_match(
                original_input, attempt.matched_term or token, attempt.match_type
            )

    # Tier 4: Synset
    attempt = find_via_synset(token, lemma, language)
    if attempt.pictogram:
        logger.debug("  SYNSET: '%s' → %d", token, attempt.pictogram.id)
        return attempt.pictogram.to_match(
            original_input, attempt.matched_term or lemma, attempt.match_type
        )

    # Tier 5: Hypernym
    attempt = find_via_hypernym(token, lemma, language)
    if attempt.pictogram:
        logger.debug("  HYPERNYM: '%s' → %d", token, attempt.pictogram.id)
        return attempt.pictogram.to_match(
            original_input,
            attempt.matched_term or lemma,
            attempt.match_type,
            confidence=attempt.confidence_override,
            )

    return None
