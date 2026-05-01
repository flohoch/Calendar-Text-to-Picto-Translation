"""
Preferred pictogram overrides.

For ambiguous keywords where multiple pictograms validly match (e.g.
"bathroom" maps to a toilet, a sink, AND a room), this dictionary lets
us hardcode the preferred pictogram ID per language.

The preference is consulted before the standard exact lookup returns its
top result. If the preferred ID is among the term's matches, it wins.
If it isn't (e.g., the override is stale or wrong), the default pick is
used silently.

To find the right ID for a term:
  1. Run the pipeline and observe which pictogram is currently picked.
  2. Browse https://arasaac.org/pictograms/search?searchText={term} —
     usually the canonical pictogram is the most downloaded.
  3. Copy that pictogram's ID into the dictionary below.

Keys must be lowercased.
"""
from __future__ import annotations

import logging

from app.models.schemas import Language

logger = logging.getLogger(__name__)

PREFERRED_PICTOGRAMS: dict[Language, dict[str, int]] = {
    Language.DE: {
        # Add overrides when encountered wrong matches.
        "aufstehen": 6549,
        "badezimmer": 33954,
        "bad": 33954,
        "zuhause":    6964,
        "küche":    33070,
        "waschküche":    29841,
        "stationsarbeit":     6624,
        "gewand":    7233,
        "zimmer":    33068,
        "mülleimer":     38205,
        "fähigkeiten":     26636,
        "freunde":     25792,
        "schwimmen":     25038,
        "allerheiligen":     32460,
        "krankenhaus": 38083,
        "speisesaal": 9824,
        "eis": 24208,
        "eissalon": 3347,
        "wäsche": 7233,
        "leiter": 35133,
    },
    Language.EN: {
        "get up": 6549,
        "bathroom": 33954,
        "family": 38351,
        "home":     6964,
        "kitchen":     33070,
        "laundry room":     29841,
        "station work":     6624,
        "clothes":     7233,
        "room":     33068,
        "friends":     25792,
        "trash bin":     38205,
        "training":     26636,
        "swimming":     25038,
        "river":     2811,
        "all saints day":     32460,
        "ophthalmologist": 38824,
    },
}


def get_preferred(concept: str, language: Language) -> int | None:
    """Return the preferred pictogram ID for `concept`, or None.

    Concepts may contain spaces — multi-word keys like "laundry room" work
    as long as the matching pipeline passes the joined phrase. This happens
    naturally for sliding-window matches.
    """
    if not concept:
        return None
    key = concept.strip().lower()
    result = PREFERRED_PICTOGRAMS.get(language, {}).get(key)
    if result is not None:
        logger.info("[preferred] '%s' → pictogram %d", key, result)
    return result
