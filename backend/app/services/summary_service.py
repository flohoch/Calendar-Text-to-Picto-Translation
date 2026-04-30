"""
SUMMARY translation pipeline:
1. Preprocessing (lowercase, strip punctuation)
2. spaCy POS tagging + lemmatization
3. German: compound splitting on nouns
4. Match each (token, lemma) through the 6-tier pipeline
5. Multi-word sliding window first
6. Generic fallback (e.g., "Aktivität" / "activity")
"""
from __future__ import annotations

import logging

from app.models.schemas import (FieldTranslation, Language, MatchType,
                                 PictogramMatch)
from app.services import (compound_splitter, lexical_dictionaries,
                          matching_pipeline, nlp_service)

logger = logging.getLogger(__name__)


def translate(text: str, language: Language) -> FieldTranslation:
    if not text or not text.strip():
        return FieldTranslation(originalText="", matches=[], unmatchedTokens=[])

    logger.info("[SUMMARY] Input: '%s'", text)

    # Tier A: Preprocessing
    normalized = text.strip()
    logger.info("[SUMMARY] Preprocessing → '%s'", normalized)

    # Tier B: spaCy POS + Lemmatization
    nlp_result = nlp_service.process(normalized, language)
    pos_lemma = [(t.text, t.pos, t.lemma) for t in nlp_result.tokens]
    logger.info("[SUMMARY] POS+Lemma → %s", pos_lemma)

    # Filter to content tokens (drop punctuation)
    content = nlp_result.content_tokens()
    if not content:
        return FieldTranslation(originalText=text, matches=[], unmatchedTokens=[])

    # Tier C: German compound splitting on nouns
    if language == Language.DE:
        expanded: list[tuple[str, str]] = []  # (text, lemma)
        for tok in content:
            if tok.pos == "NOUN":
                parts = compound_splitter.split(tok.lemma)
                if len(parts) > 1:
                    logger.info("[SUMMARY] Compound split: '%s' → %s", tok.lemma, parts)
                    for part in parts:
                        expanded.append((part, part))
                else:
                    expanded.append((tok.text.lower(), tok.lemma))
            else:
                expanded.append((tok.text.lower(), tok.lemma))
        token_lemmas = expanded
    else:
        token_lemmas = [(t.text.lower(), t.lemma) for t in content]

    logger.info("[SUMMARY] Tokens for matching → %s", token_lemmas)

    # Run 6-tier pipeline
    matches: list[PictogramMatch] = []
    unmatched: list[str] = []

    tokens = [tl[0] for tl in token_lemmas]
    lemmas = [tl[1] for tl in token_lemmas]

    i = 0
    while i < len(tokens):
        # Tier 2: Sliding window first (only on tokens for now — phrasal exact)
        if len(tokens) - i > 1:
            sw_attempt, consumed = matching_pipeline.find_sliding_window(
                tokens, i, language
            )
            if sw_attempt.pictogram and consumed > 1:
                phrase = " ".join(tokens[i : i + consumed])
                logger.info("[SUMMARY] SLIDING_WINDOW: '%s' → pictogram %d",
                            phrase, sw_attempt.pictogram.id)
                matches.append(sw_attempt.pictogram.to_match(
                    phrase, sw_attempt.matched_term or phrase, sw_attempt.match_type
                ))
                i += consumed
                continue

        token = tokens[i]
        lemma = lemmas[i]
        match = matching_pipeline.run_full_pipeline(token, lemma, language, token)
        if match:
            logger.info("[SUMMARY] %s: '%s' → pictogram %d (conf %.2f)",
                        match.match_type.value, token, match.pictogram_id,
                        match.confidence)
            matches.append(match)
        else:
            logger.info("[SUMMARY] UNMATCHED: '%s'", token)
            unmatched.append(token)
        i += 1

    # Tier 6: Generic fallback if NO matches at all
    if not matches and unmatched:
        fallback_concept = lexical_dictionaries.GENERIC_FALLBACK_CONCEPTS["summary"][language]
        from app.services import index_service
        fallback_results = index_service.find_by_exact(fallback_concept, language)
        if fallback_results:
            logger.info("[SUMMARY] GENERIC_FALLBACK: '%s' → pictogram %d",
                        fallback_concept, fallback_results[0].id)
            matches.append(fallback_results[0].to_match(
                text, fallback_concept, MatchType.GENERIC_FALLBACK
            ))

    return FieldTranslation(
        originalText=text, matches=matches, unmatchedTokens=unmatched
    )
