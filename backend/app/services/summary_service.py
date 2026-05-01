"""
SUMMARY translation pipeline:
0. Text normalization (abbreviations, phrase synonyms)
1. RAW sliding window — multi-word match against original (with stop-words),
   so phrases like "do the laundry" can be matched intact even though
   "the" is a stop word
2. spaCy POS + lemmatization
3. German: compound splitting on nouns (only if lemma not directly matchable
   AND each split part is independently matchable; otherwise the original
   is preserved)
4. Per-token matching pipeline (sliding window + exact + lemma + synset + hypernym)
5. Generic fallback ("Aktivität" / "activity")
"""
from __future__ import annotations

import logging

from app.models.schemas import (FieldTranslation, Language, MatchType,
                                PictogramMatch)
from app.services import (compound_splitter, index_service, lexical_dictionaries,
                          matching_pipeline, nlp_service, synset_service,
                          text_normalization)

logger = logging.getLogger(__name__)


def translate(text: str, language: Language) -> FieldTranslation:
    if not text or not text.strip():
        return FieldTranslation(originalText="", matches=[], unmatchedTokens=[])

    logger.info("[SUMMARY] Input: '%s'", text)

    # Tier A: Normalize abbreviations and phrase synonyms
    normalized = text_normalization.normalize(text.strip(), language)
    if normalized != text.strip():
        logger.info("[SUMMARY] Normalized: '%s' → '%s'", text, normalized)

    # Tier B: RAW sliding window over the normalized text — catches multi-word
    # ARASAAC keywords like "do the laundry" that include stop-words.
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

    # Tier B2: LEMMATIZED sliding window — try the same approach but with
    # lemmas, so phrases like "cooking dinner" hit "cook dinner" if that's
    # the ARASAAC keyword form. Skips already-consumed positions.
    nlp_for_lemmas = nlp_service.process(normalized, language)
    raw_to_lemma: dict[int, str] = {}
    nlp_tokens_alpha = [t for t in nlp_for_lemmas.tokens if not t.is_punct]
    for ridx, rtok in enumerate(raw_tokens):
        if ridx in consumed_raw_indices:
            continue
        # Best-effort match: find the first NLP token whose surface text
        # (lowercased) equals raw_tokens[ridx], and use its lemma.
        for ntok in nlp_tokens_alpha:
            if ntok.text.lower() == rtok:
                raw_to_lemma[ridx] = ntok.lemma.lower()
                break
        if ridx not in raw_to_lemma:
            raw_to_lemma[ridx] = rtok

    if raw_tokens:
        i = 0
        while i < len(raw_tokens):
            if i in consumed_raw_indices:
                i += 1
                continue
            # Build a lemma-substituted token list for the suffix starting at i.
            # Only positions not yet consumed are substituted with their lemma.
            tail_lemmas = [
                (raw_to_lemma.get(k, raw_tokens[k]) if k not in consumed_raw_indices
                 else raw_tokens[k])
                for k in range(i, len(raw_tokens))
            ]
            sw_attempt, consumed = matching_pipeline.find_sliding_window(
                tail_lemmas, 0, language
            )
            # consumed must include only currently-unconsumed positions
            if (sw_attempt.pictogram and consumed > 1
                    and not any((i + k) in consumed_raw_indices for k in range(consumed))):
                phrase = " ".join(tail_lemmas[:consumed])
                logger.info(
                    "[SUMMARY] LEMMA SLIDING_WINDOW: '%s' → pictogram %d",
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

    # Tier C: spaCy POS + Lemmatization
    nlp_result = nlp_service.process(normalized, language)
    pos_lemma = [(t.text, t.pos, t.lemma) for t in nlp_result.tokens]
    logger.info("[SUMMARY] POS+Lemma → %s", pos_lemma)

    content = nlp_result.content_tokens()
    if not content and not matches:
        return FieldTranslation(originalText=text, matches=[], unmatchedTokens=[])

    consumed_texts: set[str] = {raw_tokens[i] for i in consumed_raw_indices}

    # Tier D: prepare token list — German uses compound splitting
    if language == Language.DE:
        token_lemmas: list[tuple[str, str, str]] = []  # (text, lemma, pos)
        for tok in content:
            if tok.text.lower() in consumed_texts:
                continue

            # Skip proper nouns (names) entirely
            if tok.pos == "PROPN":
                logger.info("[SUMMARY] Skipping proper noun: '%s'", tok.text)
                continue

            # ADJ tokens are kept in the list and tried in the per-token loop;
            # unmatched ones are dropped silently there rather than added to
            # the unmatched list.

            if tok.pos == "NOUN":
                # Direct-match guard — DO NOT split if any of these resolve.
                # Try BOTH the lemma AND the original text (lowercased), since
                # spaCy's German lemmatizer occasionally returns a non-canonical
                # form that misses the index even when the surface form would hit.
                token_lower = tok.text.lower()
                lemma_lower = tok.lemma.lower()
                has_direct_match = (
                        index_service.find_by_exact(token_lower, language)
                        or index_service.find_by_exact(lemma_lower, language)
                        or index_service.find_by_lemma(lemma_lower, language)
                        or index_service.get_synsets_for_keyword(token_lower, language)
                        or index_service.get_synsets_for_keyword(lemma_lower, language)
                        or synset_service.lookup_synsets_for_word(lemma_lower, language.value)
                )
                if has_direct_match:
                    token_lemmas.append((token_lower, lemma_lower, tok.pos))
                    continue

                # Try compound splitting; require ALL parts to be matchable.
                parts = compound_splitter.split(lemma_lower)
                if len(parts) > 1 and _all_parts_matchable(parts, language):
                    logger.info("[SUMMARY] Compound split: '%s' → %s", tok.lemma, parts)
                    for part in parts:
                        token_lemmas.append((part, part, "NOUN"))
                else:
                    if len(parts) > 1:
                        logger.info(
                            "[SUMMARY] Compound split rejected (unmatchable parts): "
                            "'%s' → %s", tok.lemma, parts,
                        )
                    token_lemmas.append((token_lower, lemma_lower, tok.pos))
            else:
                token_lemmas.append((tok.text.lower(), tok.lemma, tok.pos))
    else:
        token_lemmas = [
            (t.text.lower(), t.lemma, t.pos)
            for t in content
            if t.text.lower() not in consumed_texts
               and t.pos != "PROPN"
        ]
        # Adjectives are kept in the list. They'll be tried in the per-token
        # matching loop below; if they don't resolve, they're silently dropped
        # rather than added to `unmatched`.

    if token_lemmas:
        logger.info("[SUMMARY] Tokens for matching → %s",
                    [(t, l) for t, l, _ in token_lemmas])

    # Tier E: per-token matching for the remaining tokens
    unmatched: list[str] = []
    tokens = [tl[0] for tl in token_lemmas]
    lemmas = [tl[1] for tl in token_lemmas]
    poses = [tl[2] for tl in token_lemmas]

    i = 0
    while i < len(tokens):
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
        pos = poses[i]
        match = matching_pipeline.run_full_pipeline(token, lemma, language, token)
        if match:
            logger.info("[SUMMARY] %s: '%s' → pictogram %d (conf %.2f)",
                        match.match_type.value, token, match.pictogram_id,
                        match.confidence)
            matches.append(match)
        else:
            # ADJ tokens that fail are dropped silently, not surfaced as unmatched
            if pos == "ADJ":
                logger.info("[SUMMARY] Skipping unmatched adjective: '%s'", token)
            else:
                logger.info("[SUMMARY] UNMATCHED: '%s'", token)
                unmatched.append(token)
        i += 1

    # Tier F: Generic fallback if no matches at all AND we have unmatched
    if not matches and unmatched:
        fallback_concept = lexical_dictionaries.GENERIC_FALLBACK_CONCEPTS["summary"][language]
        fallback_results = index_service.find_by_exact(fallback_concept, language)
        if fallback_results:
            logger.info("[SUMMARY] GENERIC_FALLBACK: '%s' → pictogram %d",
                        fallback_concept, fallback_results[0].id)
            matches.append(fallback_results[0].to_match(
                text, fallback_concept, MatchType.GENERIC_FALLBACK
            ))

    # Final guarantee: if NEITHER matches NOR unmatched were produced
    # (e.g. all input was filtered out by stop-words / PROPN / ADJ skipping),
    # surface every input word in the unmatched list so the user can see
    # what the system actually received.
    if not matches and not unmatched and raw_tokens:
        logger.warning(
            "[SUMMARY] No matches and no unmatched tokens — surfacing raw tokens: %s",
            raw_tokens,
        )
        unmatched = list(raw_tokens)

    logger.info("[SUMMARY] Final: %d matches, %d unmatched (%s)",
                len(matches), len(unmatched), unmatched)

    return FieldTranslation(
        originalText=text, matches=matches, unmatchedTokens=unmatched
    )


def _all_parts_matchable(parts: list[str], language: Language) -> bool:
    """
    Return True if every part has at least one resolution path
    (exact, lemma, or synset/WordNet). Used to reject pathological splits
    that produce nonsense fragments.
    """
    for part in parts:
        if not part or len(part) < 2:
            return False
        has_match = (
                index_service.find_by_exact(part, language)
                or index_service.find_by_lemma(part, language)
                or index_service.get_synsets_for_keyword(part, language)
                or synset_service.lookup_synsets_for_word(part, language.value)
        )
        if not has_match:
            return False
    return True
