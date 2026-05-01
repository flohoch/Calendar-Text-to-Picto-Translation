"""
Personal relationships dictionary.

Maps a single user's specific contacts (by first name) DIRECTLY to ARASAAC
pictogram IDs. This is intentionally per-user data: replace the entries
below to reflect the actual contacts of the user the system is configured
for.

Mapping to pictogram IDs (rather than concept words) lets you:
  - Point at any pictogram, even one whose keyword doesn't match what
    you'd write in a concept dictionary.
  - Later swap in a CUSTOM pictogram of the actual person — just upload
    the picture, get an ID, and point this dictionary at that ID. No
    pipeline changes required.

Lookup happens FIRST in the attendee pipeline, before NER and the general
lexical dictionary. This way, "Anna" reliably resolves to Anna's pictogram
rather than being detected as a person and falling back to the generic
person pictogram (id 34560).

Keys are lowercased first names.
"""
from __future__ import annotations

import logging

from app.models.schemas import Language

logger = logging.getLogger(__name__)


# Per-language, per-name → ARASAAC pictogram ID.
# The same name can map to different IDs per language if the user wants
# different captions/pictograms for different language contexts.
PERSONAL_RELATIONSHIPS: dict[Language, dict[str, int]] = {
    Language.DE: {
        "anna":   38937,
        "marina": 2422,
        "alex":   2423,
    },
    Language.EN: {
        "anna":   38937,
        "marina": 2422,
        "alex":   2423,
    },
}


def get_personal_pictogram_id(name: str, language: Language) -> int | None:
    """Return the configured pictogram ID for a known personal name, else None."""
    if not name:
        return None
    return PERSONAL_RELATIONSHIPS.get(language, {}).get(name.strip().lower())
