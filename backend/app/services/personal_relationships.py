"""
Personal relationships dictionary.

Maps a single user's specific contacts (by first name) to family-relation
concept words. This is intentionally per-user data: replace the entries
below to reflect the actual contacts of the user the system is configured
for.

Unlike the general ATTENDEE_LEXICAL dictionary (which contains universal
terms like "Mami" → mother), this dictionary holds personal names that
mean nothing to anyone else. It must be edited per-user.

Lookup happens FIRST in the attendee pipeline, before NER and the general
lexical dictionary. This way, "Anna" reliably resolves to "sister" rather
than being detected as a person and falling back to the generic person
pictogram (id 34560).
"""
from __future__ import annotations

import logging

from app.models.schemas import Language

logger = logging.getLogger(__name__)


# Personal contacts of the current user, mapped to family-relation concepts.
# Edit this table per user. Keys are lowercased first names.
PERSONAL_RELATIONSHIPS: dict[Language, dict[str, str]] = {
    Language.DE: {
        "anna": "freundin",
        "marina": "schwester",
        "alex": "bruder",
    },
    Language.EN: {
        "anna": "girlfriend",
        "marina": "sister",
        "alex": "brother",
    },
}


def get_personal_relationship(name: str, language: Language) -> str | None:
    """Return the family-relation concept for a known personal name, else None."""
    if not name:
        return None
    return PERSONAL_RELATIONSHIPS.get(language, {}).get(name.strip().lower())
