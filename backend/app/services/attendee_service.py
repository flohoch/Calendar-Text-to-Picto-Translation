"""
ATTENDEES translation pipeline.

Each attendee produces EXACTLY ONE pictogram. The original (full) attendee
text is used as the caption, so "caregiver Susan" displays the caregiver
pictogram with the caption "caregiver Susan".

Per-attendee tier order:

  1. PERSONAL_RELATIONSHIP — user-specific name → role mapping
     ("Anna" → sister, "Alex" → brother)

  2. TITLE EXTRACTION — split off honorifics/role-words like "Dr.",
     "Doctor", "Caregiver", "Teacher", and resolve them via the
     attendee lexical dictionary. If a doctor-type title is detected,
     the SUMMARY context is consulted to pick the specialist pictogram
     (e.g. "Dr. Müller" + summary "Zahnarzttermin" → dentist pictogram).

  3. LEXICAL_DICT — universal family/title terms (Mami → mother)
     applied to the whole attendee text.

  4. NER PERSON FALLBACK — any remaining unresolved name uses the
     generic person pictogram (id 34560).

  5. GENERIC_FALLBACK — generic person pictogram if all else fails.
"""
from __future__ import annotations

import logging
import re

from app.models.schemas import (AttendeeTranslation, Language, MatchType,
                                PictogramMatch, Pictogram)
from app.services import (index_service, lexical_dictionaries,
                          matching_pipeline, nlp_service,
                          personal_relationships, text_normalization)
from app.services.lexical_dictionaries import GENERIC_PERSON_PICTOGRAM_ID

logger = logging.getLogger(__name__)


# Doctor-specialty cues from summary context.
# Maps regex pattern → ARASAAC concept word for the specialist pictogram.
# Searched in order; first hit wins.
DOCTOR_SPECIALTY_CUES: dict[Language, list[tuple[str, str]]] = {
    Language.EN: [
        (r"\b(dentist|tooth|teeth|dental|orthodont)", "dentist"),
        (r"\b(eye|vision|ophthalm|optometr)",        "ophthalmologist"),
        (r"\b(skin|dermat|derm)",                     "dermatologist"),
        (r"\b(ear|hearing|audi|otolaryng)",           "otolaryngologist"),
        (r"\b(physi|physio|physical therap)",         "physiotherapist"),
        (r"\b(psych|therap|counsel)",                 "psychologist"),
        (r"\b(speech|logopedic|logoped)",             "speech therapist"),
        (r"\b(pediatric|children|kids)",              "pediatrician"),
        (r"\b(vet|veterin|animal)",                   "veterinarian"),
    ],
    Language.DE: [
        (r"\b(zahn|kiefer|orthodont|kieferorthopäd)", "zahnarzt"),
        (r"\b(augen|ophthalm)",                        "augenarzt"),
        (r"\b(haut|dermatolog)",                       "hautarzt"),
        (r"\b(ohr|hno|hals)",                          "hno-arzt"),
        (r"\b(physio|physikalisch)",                   "physiotherapeut"),
        (r"\b(psych|therap|beratung)",                 "psychologe"),
        (r"\b(logopäd|sprach)",                        "logopäde"),
        (r"\b(kinder|pädiatr)",                        "kinderarzt"),
        (r"\b(tierarzt|veterin|tier)",                 "tierarzt"),
    ],
}

# Generic doctor pictogram IDs per language (user-specified for English).
DEFAULT_DOCTOR_ID: dict[Language, int] = {
    Language.EN: 38857,
    Language.DE: 38857,  # adjust if your German "Arzt" pictogram has a different canonical ID
}

# Title regex per language. The title MUST be at the START of the attendee
# text to be considered. Captures the rest (the personal name) into group 2.
TITLE_PATTERNS: dict[Language, list[tuple[str, str]]] = {
    Language.EN: [
        # (pattern, normalized_title_concept)
        (r"^(dr\.?|doctor)\s+(.+)$",                      "doctor"),
        (r"^(caregiver)\s+(.+)$",                          "caregiver"),
        (r"^(nurse)\s+(.+)$",                              "nurse"),
        (r"^(teacher)\s+(.+)$",                            "teacher"),
        (r"^(instructor)\s+(.+)$",                         "instructor"),
        (r"^(tutor)\s+(.+)$",                              "tutor"),
        (r"^(trainer)\s+(.+)$",                            "trainer"),
        (r"^(coach)\s+(.+)$",                              "coach"),
        (r"^(mentor)\s+(.+)$",                             "mentor"),
        (r"^(therapist)\s+(.+)$",                          "therapist"),
        (r"^(speech therapist|logopedist)\s+(.+)$",        "speech therapist"),
        (r"^(physiotherapist|physical therapist)\s+(.+)$", "physiotherapist"),
        (r"^(prof\.?|professor)\s+(.+)$",                  "professor"),
        (r"^(hr manager|hr|human resources)\s+(.+)$",      "hr manager"),
        (r"^(manager)\s+(.+)$",                            "manager"),
        (r"^(employee)\s+(.+)$",                           "employee"),
        (r"^(bank employee|banker)\s+(.+)?$",              "bank employee"),
    ],
    Language.DE: [
        (r"^(dr\.?|doktor)\s+(.+)$",                       "arzt"),
        (r"^(prof\.?|professor(?:in)?)\s+(.+)$",           "professor"),
        (r"^(betreuer(?:in)?)\s+(.+)$",                    "betreuer"),
        (r"^(pflegerin|pfleger)\s+(.+)$",                  "pfleger"),
        (r"^(krankenschwester|krankenpfleger)\s+(.+)$",    "krankenschwester"),
        (r"^(lehrer(?:in)?)\s+(.+)$",                      "lehrer"),
        (r"^(therapeut(?:in)?)\s+(.+)$",                   "therapeut"),
        (r"^(logopäd(?:e|in))\s+(.+)$",                    "logopäde"),
        (r"^(physiotherapeut(?:in)?)\s+(.+)$",             "physiotherapeut"),
        (r"^(psycholog(?:e|in))\s+(.+)$",                  "psychologe"),
        (r"^(trainer(?:in)?)\s+(.+)$",                     "trainer"),
        (r"^(personaler(?:in)?|personalreferent(?:in)?)\s+(.+)$", "hr manager"),
        (r"^(manager(?:in)?)\s+(.+)$",                     "manager"),
    ],
}


def translate(text: str, language: Language,
              summary_context: str = "") -> list[AttendeeTranslation]:
    if not text or not text.strip():
        return []

    logger.info("[ATTENDEES] Input: '%s'", text)
    raw_attendees = [a.strip() for a in text.split(",") if a.strip()]
    logger.info("[ATTENDEES] Split (comma) → %s", raw_attendees)

    return [
        _translate_single(attendee, language, summary_context)
        for attendee in raw_attendees
    ]


def _translate_single(attendee: str, language: Language,
                      summary_context: str) -> AttendeeTranslation:
    """Resolve a single attendee to ONE pictogram, captioned with the original text."""
    logger.info("[ATTENDEES] Processing: '%s'", attendee)
    lower = attendee.lower().strip()

    # Tier 1: Personal relationships (user-specific names → direct pictogram ID)
    personal_id = personal_relationships.get_personal_pictogram_id(lower, language)
    if personal_id is not None:
        picto = index_service.get_pictogram_by_id(personal_id, language)
        if picto:
            logger.info(
                "[ATTENDEES] PERSONAL_RELATIONSHIP: '%s' → pictogram %d",
                lower, personal_id,
            )
            return _wrap(attendee, picto, MatchType.PERSONAL_RELATIONSHIP, attendee)
        else:
            logger.warning(
                "[ATTENDEES] PERSONAL_RELATIONSHIP: '%s' → id %d not found in DB",
                lower, personal_id,
            )

    # Tier 2: Title extraction. If the attendee starts with a known title,
    # resolve the title to a concept (with doctor disambiguation if applicable)
    # and ignore the personal name part for pictogram selection.
    title_match = _extract_title(lower, language)
    if title_match is not None:
        title_concept, _personal_name = title_match
        # Doctor disambiguation: if the title resolved to a doctor concept,
        # check the summary for specialty cues.
        specialty_concept = _doctor_specialty_from_summary(
            title_concept, summary_context, language
        )
        chosen_concept = specialty_concept or title_concept

        picto = _resolve_concept(chosen_concept, language)
        if picto is None and chosen_concept != title_concept:
            # specialty couldn't be resolved — fall back to the generic title
            picto = _resolve_concept(title_concept, language)
        if picto is None and title_concept in ("doctor", "arzt"):
            # final fallback to hardcoded doctor pictogram ID
            picto = index_service.get_pictogram_by_id(
                DEFAULT_DOCTOR_ID[language], language
            )
        if picto:
            log_extra = (
                f" (specialty='{specialty_concept}')" if specialty_concept else ""
            )
            logger.info(
                "[ATTENDEES] TITLE: '%s' → concept '%s'%s → pictogram %d",
                attendee, chosen_concept, log_extra, picto.id,
            )
            return _wrap(attendee, picto, MatchType.LEXICAL_DICT, chosen_concept)

    # Tier 3: Universal family/title lexical dictionary (whole-text match)
    concept_aliases = lexical_dictionaries.get_attendee_lexical(lower, language)
    if concept_aliases:
        for concept in concept_aliases:
            picto = _resolve_concept(concept, language)
            if picto:
                return _wrap(attendee, picto, MatchType.LEXICAL_DICT, concept)
        logger.info(
            "[ATTENDEES] LEXICAL_DICT: '%s' had aliases %s but none resolved",
            lower, concept_aliases,
        )

    # Tier 4: NER PERSON detection → generic person pictogram
    nlp_result = nlp_service.process(attendee, language)
    person_labels = {"PER", "PERSON"}
    if any(e.label in person_labels for e in nlp_result.entities):
        picto = index_service.get_pictogram_by_id(
            GENERIC_PERSON_PICTOGRAM_ID, language
        )
        if picto:
            logger.info(
                "[ATTENDEES] NER_PERSON_FALLBACK: '%s' → pictogram %d",
                attendee, GENERIC_PERSON_PICTOGRAM_ID,
            )
            return _wrap(attendee, picto, MatchType.NER_PERSON_FALLBACK, attendee)

    # Tier 5: Last-ditch — try the standard matching pipeline on the lemma
    if nlp_result.tokens:
        first_content = next(
            (t for t in nlp_result.tokens if t.is_alpha and not t.is_punct),
            None,
        )
        if first_content:
            m = matching_pipeline.run_full_pipeline(
                first_content.text.lower(), first_content.lemma,
                language, attendee,
            )
            if m:
                logger.info(
                    "[ATTENDEES] %s: '%s' → pictogram %d",
                    m.match_type.value, attendee, m.pictogram_id,
                )
                # Override the matched_term with the full attendee text for the caption
                m.matched_term = attendee
                return AttendeeTranslation(
                    originalAttendee=attendee, matches=[m], unmatchedTokens=[]
                )

    # Tier 6: Generic person fallback
    fallback = index_service.get_pictogram_by_id(
        GENERIC_PERSON_PICTOGRAM_ID, language
    )
    if fallback:
        logger.info(
            "[ATTENDEES] GENERIC_FALLBACK: '%s' → pictogram %d",
            attendee, GENERIC_PERSON_PICTOGRAM_ID,
        )
        return _wrap(attendee, fallback, MatchType.NER_PERSON_FALLBACK, attendee)

    return AttendeeTranslation(
        originalAttendee=attendee, matches=[], unmatchedTokens=[attendee]
    )


def _extract_title(lower_attendee: str, language: Language) -> tuple[str, str] | None:
    """Match the attendee text against title patterns. Return (concept, name) if matched."""
    for pattern, concept in TITLE_PATTERNS.get(language, []):
        m = re.match(pattern, lower_attendee, flags=re.IGNORECASE)
        if m:
            return concept, m.group(2)
    return None


def _doctor_specialty_from_summary(title_concept: str,
                                   summary: str,
                                   language: Language) -> str | None:
    """If title is doctor-like, scan summary for specialty cues."""
    if title_concept not in ("doctor", "arzt"):
        return None
    if not summary or not summary.strip():
        return None
    # Apply text normalization to the summary first so abbreviations are
    # expanded before regex matching.
    normalized_summary = text_normalization.normalize(summary, language).lower()
    for pattern, concept in DOCTOR_SPECIALTY_CUES.get(language, []):
        if re.search(pattern, normalized_summary, flags=re.IGNORECASE):
            logger.info(
                "[ATTENDEES] doctor specialty cue '%s' matched in summary → '%s'",
                pattern, concept,
            )
            return concept
    return None


def _resolve_concept(concept: str, language: Language) -> Pictogram | None:
    """Resolve a concept word to a pictogram via the exact index."""
    if not concept:
        return None
    results = index_service.find_by_exact(concept, language)
    return results[0] if results else None


def _wrap(attendee: str, picto: Pictogram, match_type: MatchType,
          matched_term: str) -> AttendeeTranslation:
    """Build a single-match AttendeeTranslation captioned with the FULL attendee text."""
    match = picto.to_match(attendee, attendee, match_type)
    # Override matched_term to include the full original attendee for the caption
    # (the to_match method sets matched_term to the second argument by default,
    # which we already passed as `attendee`). Keep the *internal* matched concept
    # accessible via the log line; the user-facing caption is the attendee text.
    return AttendeeTranslation(
        originalAttendee=attendee, matches=[match], unmatchedTokens=[]
    )
