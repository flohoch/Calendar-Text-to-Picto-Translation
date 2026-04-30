"""
ATTENDEES translation pipeline:
0. Split input on commas → list of individual attendees
For each attendee:
  1. PERSONAL_RELATIONSHIP — user-specific name → role mapping (e.g. Anna → sister)
  2. LEXICAL_DICT — universal family/title terms (Mami → mother, Dr. → doctor)
  3. NER — if PERSON entity, fall back to generic person pictogram (id 34560)
  4. Standard 6-tier matching
  5. GENERIC_FALLBACK — generic person pictogram if nothing else worked
"""
from __future__ import annotations

import logging

from app.models.schemas import (AttendeeTranslation, Language, MatchType,
                                PictogramMatch)
from app.services import (index_service, lexical_dictionaries,
                          matching_pipeline, nlp_service,
                          personal_relationships)
from app.services.lexical_dictionaries import GENERIC_PERSON_PICTOGRAM_ID

logger = logging.getLogger(__name__)


def translate(text: str, language: Language) -> list[AttendeeTranslation]:
    if not text or not text.strip():
        return []

    logger.info("[ATTENDEES] Input: '%s'", text)
    raw_attendees = [a.strip() for a in text.split(",") if a.strip()]
    logger.info("[ATTENDEES] Split (comma) → %s", raw_attendees)

    return [_translate_single_attendee(a, language) for a in raw_attendees]


def _translate_single_attendee(attendee: str, language: Language) -> AttendeeTranslation:
    logger.info("[ATTENDEES] Processing: '%s'", attendee)
    lower = attendee.lower().strip()

    # Tier 1: Personal relationships (user-specific names)
    personal_concept = personal_relationships.get_personal_relationship(lower, language)
    if personal_concept:
        picto_results = index_service.find_by_exact(personal_concept, language)
        if picto_results:
            logger.info("[ATTENDEES] PERSONAL_RELATIONSHIP: '%s'→'%s' → pictogram %d",
                        lower, personal_concept, picto_results[0].id)
            match = picto_results[0].to_match(
                attendee, personal_concept, MatchType.PERSONAL_RELATIONSHIP
            )
            return AttendeeTranslation(
                originalAttendee=attendee, matches=[match], unmatchedTokens=[]
            )

    # Tier 2: Universal family/title lexical dictionary
    concept = lexical_dictionaries.get_attendee_lexical(lower, language)
    if concept:
        picto_results = index_service.find_by_exact(concept, language)
        if picto_results:
            logger.info("[ATTENDEES] LEXICAL_DICT: '%s'→'%s' → pictogram %d",
                        lower, concept, picto_results[0].id)
            match = picto_results[0].to_match(
                attendee, concept, MatchType.LEXICAL_DICT
            )
            return AttendeeTranslation(
                originalAttendee=attendee, matches=[match], unmatchedTokens=[]
            )

    # Tier 3: NER for PERSON
    nlp_result = nlp_service.process(attendee, language)
    person_labels = {"PER", "PERSON"}
    person_entity = next(
        (e for e in nlp_result.entities if e.label in person_labels), None
    )
    if person_entity:
        logger.info("[ATTENDEES] NER detected PERSON: '%s'", person_entity.text)
        first_token = person_entity.text.split()[0].lower()
        attempt_match = matching_pipeline.run_full_pipeline(
            first_token, first_token, language, attendee
        )
        if attempt_match:
            return AttendeeTranslation(
                originalAttendee=attendee,
                matches=[attempt_match],
                unmatchedTokens=[],
            )

        fallback = index_service.get_pictogram_by_id(
            GENERIC_PERSON_PICTOGRAM_ID, language
        )
        if fallback:
            logger.info("[ATTENDEES] NER_PERSON_FALLBACK: '%s' → pictogram %d",
                        attendee, GENERIC_PERSON_PICTOGRAM_ID)
            match = fallback.to_match(
                attendee, attendee, MatchType.NER_PERSON_FALLBACK
            )
            return AttendeeTranslation(
                originalAttendee=attendee, matches=[match], unmatchedTokens=[]
            )

    # Tier 4: Token-level pipeline
    content = nlp_result.content_tokens()
    matches: list[PictogramMatch] = []
    unmatched: list[str] = []
    for tok in content:
        m = matching_pipeline.run_full_pipeline(
            tok.text.lower(), tok.lemma, language, attendee
        )
        if m:
            logger.info("[ATTENDEES] %s: '%s' → pictogram %d (conf %.2f)",
                        m.match_type.value, tok.text, m.pictogram_id, m.confidence)
            matches.append(m)
        else:
            unmatched.append(tok.text.lower())

    # Tier 5: Generic fallback to person pictogram
    if not matches:
        fallback = index_service.get_pictogram_by_id(
            GENERIC_PERSON_PICTOGRAM_ID, language
        )
        if fallback:
            logger.info(
                "[ATTENDEES] GENERIC_FALLBACK (person): '%s' → pictogram %d",
                attendee, GENERIC_PERSON_PICTOGRAM_ID,
            )
            matches.append(fallback.to_match(
                attendee, attendee, MatchType.NER_PERSON_FALLBACK
            ))

    return AttendeeTranslation(
        originalAttendee=attendee, matches=matches, unmatchedTokens=unmatched
    )
