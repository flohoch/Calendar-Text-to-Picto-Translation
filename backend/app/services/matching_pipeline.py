"""
Shared 6-tier matching pipeline. Used by summary/location/attendee services.

Tiers:
1. EXACT keyword match
2. SLIDING_WINDOW (multi-word exact)
3. LEMMA lookup
4. SYNSET lookup (ARASAAC-WN)
5. HYPERNYM traversal (1-2 levels)
6. (Generic fallback handled by caller — depends on category)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.models.schemas import Language, MatchType, Pictogram, PictogramMatch
from app.services import index_service, synset_service

logger = logging.getLogger(__name__)

HYPERNYM_MAX_DEPTH = 2


@dataclass
class MatchAttempt:
    """Result of attempting to match a single token/phrase."""
    pictogram: Pictogram | None = None
    match_type: MatchType | None = None
    confidence_override: float | None = None
    matched_term: str | None = None


def find_for_phrase(phrase: str, language: Language) -> MatchAttempt:
    """Tier 1: exact match (works for both single words and multi-word phrases)."""
    results = index_service.find_by_exact(phrase, language)
    if results:
        return MatchAttempt(
            pictogram=results[0],
            match_type=MatchType.EXACT,
            matched_term=phrase,
        )
    return MatchAttempt()


def find_sliding_window(tokens: list[str], start: int,
                        language: Language) -> tuple[MatchAttempt, int]:
    """
    Tier 2: try to match the longest possible phrase starting at `start`,
    shrinking until a match or a single token. Returns (match, consumed_count).
    """
    n = len(tokens)
    for window_size in range(n - start, 1, -1):
        phrase = " ".join(tokens[start : start + window_size])
        results = index_service.find_by_exact(phrase, language)
        if results:
            return (
                MatchAttempt(
                    pictogram=results[0],
                    match_type=MatchType.SLIDING_WINDOW,
                    matched_term=phrase,
                ),
                window_size,
            )
    return MatchAttempt(), 0


def find_for_lemma(lemma: str, language: Language) -> MatchAttempt:
    """Tier 3: lemma lookup."""
    results = index_service.find_by_lemma(lemma, language)
    if results:
        return MatchAttempt(
            pictogram=results[0],
            match_type=MatchType.LEMMA,
            matched_term=lemma,
        )
    return MatchAttempt()


def find_via_synset(token: str, lemma: str, language: Language) -> MatchAttempt:
    """Tier 4: direct synset match."""
    candidate_synsets: set[str] = set()
    candidate_synsets.update(index_service.get_synsets_for_keyword(token, language))
    if lemma != token:
        candidate_synsets.update(index_service.get_synsets_for_keyword(lemma, language))

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
    """Tier 5: hypernym traversal up to max_depth levels."""
    if not synset_service.is_available():
        return MatchAttempt()

    candidate_synsets: set[str] = set()
    candidate_synsets.update(index_service.get_synsets_for_keyword(token, language))
    if lemma != token:
        candidate_synsets.update(index_service.get_synsets_for_keyword(lemma, language))

    if not candidate_synsets:
        return MatchAttempt()

    hypernym_levels = synset_service.get_hypernyms_for_all(
        candidate_synsets, max_depth=max_depth
    )
    for level_idx, level_ids in enumerate(hypernym_levels):
        matches = index_service.find_by_any_synset(level_ids, language)
        if matches:
            # Confidence decreases with depth
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
    Run tiers 1, 3, 4, 5 for a single token (sliding window is invoked separately
    by callers that operate on multi-token sequences).
    Returns the first successful match, or None.
    """
    # Tier 1: Exact
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
