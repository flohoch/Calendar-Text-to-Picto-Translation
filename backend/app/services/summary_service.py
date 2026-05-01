"""
SUMMARY translation pipeline:
0. Text normalization (abbreviations, phrase synonyms)
1. RAW sliding window — multi-word match against original (with stop-words),
   so phrases like "do the laundry" can be matched intact even though
   "the" is a stop word
2. spaCy POS + lemmatization
3. German: compound splitting on nouns (only if lemma not directly matchable)
4. Per-token matching pipeline (sliding window + exact + lemma + synset + hypernym)
5. Generic fallback ("Aktivität" / "activity")
"""
from __future__ import annotations

import logging

from app.models.schemas import (FieldTranslation, Language, MatchType,
                                PictogramMatch)
from app.services import (compound_splitter, index_service, lexical_dictionaries,
                          matching_pipeline, nlp_service, text_normalization)

logger = logging.getLogger(__name__)


def translate(text: str, language: Language) -> FieldTranslation:
    if not text or not text.strip():
        return FieldTranslation(originalText="", matches=[], unmatchedTokens=[])

    logger.info("[SUMMARY] Input: '%s'", text)

    # Tier A: Normalize abbreviations and phrase synonyms
    normalized = text_normalization.normalize(text.strip(), language)
    if normalized != text.strip():
        logger.info("[SUMMARY] Normalized: '%s' → '%s'", text, normalized)

    # Tier B: RAW sliding window over the normalized text — this catches
    # multi-word ARASAAC keywords like "do the laundry" that include
    # stop-words spaCy would otherwise filter out.
    matches: list[PictogramMatch] = []
    raw_tokens = [t.lower() for t in normalized.split() if t.strip()]
    consumed_raw_indices: set[int] = set()

    if raw_tokens:
        i = 0
        while i < len(raw_tokens):
            sw_attempt, consumed = matching_pipeline.find_sliding_window(
                raw_tokens, i, language
            )
            if sw_attempt.pictogram and consumed > 1:
                phrase = " ".join(raw_tokens[i : i + consumed])
                logger.info(
                    "[SUMMARY] RAW SLIDING_WINDOW: '%s' → pictogram %d",
                    phrase, sw_attempt.pictogram.id,
                )
                matches.append(sw_attempt.pictogram.to_match(
                    phrase, sw_attempt.matched_term or phrase, sw_attempt.match_type
                ))
                for k in range(i, i + consumed):
                    consumed_raw_indices.add(k)
                i += consumed
            else:
                i += 1

    # If the raw sliding window covered everything substantive, we can stop.
    # But to keep the rest of the pipeline (POS, lemma, etc.) effective on
    # uncovered tokens, run NLP on the full normalized string and skip any
    # tokens already consumed.

    # Tier C: spaCy POS + Lemmatization on normalized text
    nlp_result = nlp_service.process(normalized, language)
    pos_lemma = [(t.text, t.pos, t.lemma) for t in nlp_result.tokens]
    logger.info("[SUMMARY] POS+Lemma → %s", pos_lemma)

    content = nlp_result.content_tokens()
    if not content and not matches:
        return FieldTranslation(originalText=text, matches=[], unmatchedTokens=[])

    # Build a set of consumed-by-raw-sliding-window lowercased token texts to
    # avoid double-matching what was already covered.
    consumed_texts: set[str] = {raw_tokens[i] for i in consumed_raw_indices}

    # Tier D: German compound splitting on nouns — only if the lemma itself
    # cannot be resolved by ANY direct lookup, including WordNet.
    # The WordNet check matters for compounds like "Kieferorthopäde" whose
    # parts ("Kiefer" = tree, "Orthopäde" = orthopedist) are both in the
    # vocabulary but mean nothing close to the compound's meaning. If
    # the synset/hypernym tier can resolve the compound, we must let it.
    if language == Language.DE:
        from app.services import synset_service
        expanded: list[tuple[str, str]] = []
        for tok in content:
            if tok.text.lower() in consumed_texts:
                continue

            # Skip proper nouns entirely — they shouldn't be translated.
            # Names ("Tom", "Lukas") would otherwise be lemmatized and
            # tossed into the matching pipeline, where hypernym traversal
            # tends to land on inappropriate results ("person with autism"
            # instead of just "person", or worse, a celebrity-themed pictogram).
            if tok.pos == "PROPN":
                logger.info("[SUMMARY] Skipping proper noun: '%s'", tok.text)
                continue

            if tok.pos == "NOUN":
                has_direct_match = (
                        index_service.find_by_exact(tok.lemma, language)
                        or index_service.find_by_lemma(tok.lemma, language)
                        or index_service.get_synsets_for_keyword(tok.lemma, language)
                        or synset_service.lookup_synsets_for_word(tok.lemma)
                )
                if has_direct_match:
                    expanded.append((tok.text.lower(), tok.lemma))
                    continue

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
        token_lemmas = [
            (t.text.lower(), t.lemma)
            for t in content
            # Skip proper nouns in English too — see rationale above.
            if t.text.lower() not in consumed_texts and t.pos != "PROPN"
        ]

    if token_lemmas:
        logger.info("[SUMMARY] Tokens for matching → %s", token_lemmas)

    # Tier E: per-token matching for tokens not consumed by raw sliding window
    unmatched: list[str] = []
    tokens = [tl[0] for tl in token_lemmas]
    lemmas = [tl[1] for tl in token_lemmas]

    i = 0
    while i < len(tokens):
        # Filtered sliding window over the (smaller) content-token list
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

    # Tier F: Generic fallback if no matches at all
    if not matches and unmatched:
        fallback_concept = lexical_dictionaries.GENERIC_FALLBACK_CONCEPTS["summary"][language]
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
