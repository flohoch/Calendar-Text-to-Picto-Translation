"""
LOCATION translation pipeline:
1. Apply NER to detect organization/location entities
2. CONTEXT-AWARE DISAMBIGUATION — if the location is ambiguous (e.g.
   "bank"), use the summary text to pick the right interpretation
3. Lexical lookup (Hofer→supermarkt, AKH→krankenhaus, etc.)
4. spaCy lemmatization
5. Standard 6-tier matching
6. Generic location fallback ("Ort" / "place")
"""
from __future__ import annotations

import logging

from app.models.schemas import (FieldTranslation, Language, MatchType,
                                PictogramMatch)
from app.services import (disambiguation_dictionaries, index_service,
                          lexical_dictionaries, matching_pipeline, nlp_service,
                          text_normalization)

logger = logging.getLogger(__name__)


def translate(text: str, language: Language,
              summary_context: str = "") -> FieldTranslation:
    """
    Translate the LOCATION field. `summary_context` is the (raw) summary
    text from the same calendar event; it is used for disambiguation of
    ambiguous location terms.
    """
    if not text or not text.strip():
        return FieldTranslation(originalText="", matches=[], unmatchedTokens=[])

    # Normalize abbreviations in the location text. Note that location-specific
    # abbreviations (Hofer, AKH, etc.) are still resolved by the lexical
    # dictionary later — normalization only handles generic shortforms.
    normalized = text_normalization.normalize(text.strip(), language)
    if normalized != text.strip():
        logger.info("[LOCATION] Normalized: '%s' → '%s'", text, normalized)

    logger.info("[LOCATION] Input: '%s' (summary context: '%s')",
                normalized, summary_context)

    # Tier A: NER
    nlp_result = nlp_service.process(normalized, language)
    entities = [(e.text, e.label) for e in nlp_result.entities]
    logger.info("[LOCATION] NER entities → %s", entities)

    matches: list[PictogramMatch] = []

    # Tier B: Context-aware disambiguation
    disambig_concept, disambig_pid = disambiguation_dictionaries.disambiguate_location(
        text, summary_context, language
    )
    if disambig_pid is not None:
        picto = index_service.get_pictogram_by_id(disambig_pid, language)
        if picto:
            logger.info(
                "[LOCATION] DISAMBIGUATED (id): '%s' (via summary='%s') → pictogram %d",
                text, summary_context, picto.id,
            )
            matches.append(picto.to_match(
                text, disambig_concept or text, MatchType.DISAMBIGUATED
            ))
            return FieldTranslation(originalText=text, matches=matches, unmatchedTokens=[])

    if disambig_concept:
        # Try the concept directly, then a few common aliases for it.
        # This makes the dict tolerant to ARASAAC keyword variations.
        aliases = [disambig_concept]
        if disambig_concept == "parkbank":
            aliases += ["sitzbank", "park", "bench"]
        elif disambig_concept == "river":
            aliases += ["riverbank", "shore"]
        for alias in aliases:
            results = index_service.find_by_exact(alias, language)
            if results:
                logger.info(
                    "[LOCATION] DISAMBIGUATED: '%s' (via summary='%s') → '%s' → pictogram %d",
                    text, summary_context, alias, results[0].id,
                )
                matches.append(results[0].to_match(
                    text, alias, MatchType.DISAMBIGUATED
                ))
                return FieldTranslation(originalText=text, matches=matches, unmatchedTokens=[])

    # Tier B2: Location title patterns — "Friseur Bundy" → friseursalon.
    # The title (a profession/business word) is at the start; the rest is
    # treated as a name/identifier and ignored for picture selection.
    title_concept = _extract_location_title(normalized.strip().lower(), language)
    if title_concept:
        for alias in title_concept:
            results = index_service.find_by_exact(alias, language)
            if results:
                logger.info(
                    "[LOCATION] TITLE: '%s' → '%s' → pictogram %d",
                    text, alias, results[0].id,
                )
                matches.append(results[0].to_match(
                    text, alias, MatchType.LEXICAL_DICT
                ))
                return FieldTranslation(originalText=text, matches=matches, unmatchedTokens=[])

    # Tier C: Lexical lookup — try the whole (normalized) text, each entity,
    # AND each individual word. Per-word lookup catches Austria/region-specific
    # acronyms like "AMS" in "AMS Vienna" that NER doesn't recognize as ORG.
    candidates: list[str] = [normalized.strip().lower()]
    for ent in nlp_result.entities:
        candidates.append(ent.text.strip().lower())
    # Per-word fallback
    for word in normalized.strip().lower().split():
        if word:
            candidates.append(word)
    seen = set()
    candidates = [c for c in candidates if c and not (c in seen or seen.add(c))]

    for cand in candidates:
        concept_aliases = lexical_dictionaries.get_location_lexical(cand, language)
        if not concept_aliases:
            continue
        for concept in concept_aliases:
            results = index_service.find_by_exact(concept, language)
            if results:
                logger.info("[LOCATION] LEXICAL_DICT: '%s'→'%s' → pictogram %d",
                            cand, concept, results[0].id)
                matches.append(results[0].to_match(
                    text, concept, MatchType.LEXICAL_DICT
                ))
                return FieldTranslation(originalText=text, matches=matches, unmatchedTokens=[])
        logger.info(
            "[LOCATION] LEXICAL_DICT: '%s' had aliases %s but none resolved in the index",
            cand, concept_aliases,
        )

    # Tier D: token-level pipeline (with sliding window)
    content = nlp_result.content_tokens()
    tokens = [t.text.lower() for t in content]
    lemmas = [t.lemma for t in content]
    unmatched: list[str] = []

    i = 0
    while i < len(tokens):
        if len(tokens) - i > 1:
            sw_attempt, consumed = matching_pipeline.find_sliding_window(
                tokens, i, language
            )
            if sw_attempt.pictogram and consumed > 1:
                phrase = " ".join(tokens[i : i + consumed])
                logger.info("[LOCATION] SLIDING_WINDOW: '%s' → pictogram %d",
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
            logger.info("[LOCATION] %s: '%s' → pictogram %d (conf %.2f)",
                        match.match_type.value, token, match.pictogram_id,
                        match.confidence)
            matches.append(match)
        else:
            unmatched.append(token)
            logger.info("[LOCATION] UNMATCHED: '%s'", token)
        i += 1

    # Tier E: Generic fallback if no matches
    if not matches:
        fallback_concept = lexical_dictionaries.GENERIC_FALLBACK_CONCEPTS["location"][language]
        results = index_service.find_by_exact(fallback_concept, language)
        if results:
            logger.info("[LOCATION] GENERIC_FALLBACK: '%s' → pictogram %d",
                        fallback_concept, results[0].id)
            matches.append(results[0].to_match(
                text, fallback_concept, MatchType.GENERIC_FALLBACK
            ))

    return FieldTranslation(
        originalText=text, matches=matches, unmatchedTokens=unmatched
    )


# Location title patterns — when the location text begins with a known
# profession or business type, treat that word as the location concept and
# ignore the trailing name/identifier. The list of aliases is tried in order
# against the exact index until one matches.
_LOCATION_TITLE_PATTERNS_DE: list[tuple[str, list[str]]] = [
    (r"^friseur(in)?\s+\w+", ["friseursalon", "friseur"]),
    (r"^bäckerei\s+\w+",     ["bäckerei"]),
    (r"^metzgerei\s+\w+",    ["metzgerei"]),
    (r"^apotheke\s+\w+",     ["apotheke"]),
    (r"^restaurant\s+\w+",   ["restaurant"]),
    (r"^café\s+\w+",         ["café", "cafe"]),
    (r"^hotel\s+\w+",        ["hotel"]),
]
_LOCATION_TITLE_PATTERNS_EN: list[tuple[str, list[str]]] = [
    (r"^hairdresser\s+\w+",   ["hair salon", "hairdresser"]),
    (r"^bakery\s+\w+",         ["bakery"]),
    (r"^butcher\s+\w+",        ["butcher", "butcher shop"]),
    (r"^pharmacy\s+\w+",       ["pharmacy"]),
    (r"^restaurant\s+\w+",     ["restaurant"]),
    (r"^cafe\s+\w+",           ["cafe"]),
    (r"^hotel\s+\w+",          ["hotel"]),
    (r".*\bworkshop\b.*",      ["workshop"]),
    (r".*\bgym\b.*",           ["gym"]),
    (r".*\boffice\b.*",        ["office"]),
]


def _extract_location_title(lower_text: str, language: Language) -> list[str] | None:
    import re as _re
    patterns = _LOCATION_TITLE_PATTERNS_DE if language == Language.DE else _LOCATION_TITLE_PATTERNS_EN
    for pattern, aliases in patterns:
        if _re.match(pattern, lower_text, flags=_re.IGNORECASE):
            return aliases
    return None
