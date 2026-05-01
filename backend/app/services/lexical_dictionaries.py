"""
Hand-curated lexical dictionaries that map common shortcuts/brand names to
ARASAAC-relevant concept words. Concepts are looked up in the pictogram
index, so we don't hardcode pictogram IDs (which makes this robust to
ARASAAC database changes).

Values may be either a single concept string OR a list of fallback aliases.
When a list is provided, each alias is tried in order against the index
until one resolves; this matters when the most natural concept word
(e.g. "job center") isn't an ARASAAC keyword but a synonym is
(e.g. "employment office").
"""
from app.models.schemas import Language


# --- Location dictionaries ---
# Brand names / abbreviations → ARASAAC concept word (or list of fallbacks)

LOCATION_LEXICAL: dict[Language, dict[str, str | list[str]]] = {
    Language.DE: {
        # Supermarkets (Austria/Germany)
        "hofer": "supermarkt",
        "spar": "supermarkt",
        "billa": "supermarkt",
        "merkur": "supermarkt",
        "lidl": "supermarkt",
        "aldi": "supermarkt",
        "rewe": "supermarkt",
        "edeka": "supermarkt",
        "penny": "supermarkt",
        # Hospitals
        "akh": "krankenhaus",
        "spital": "krankenhaus",
        "klinik": "krankenhaus",
        # Pharmacies
        "apotheke": "apotheke",
        "bipa": "drogerie",
        "dm": "drogerie",
        # Schools
        "schule": "schule",
        "vs": "schule",          # Volksschule
        "ahs": "schule",
        "nms": "schule",
        # Transit
        "bahnhof": "bahnhof",
        "öbb": "bahnhof",
        "u-bahn": "u_bahn",
        "wiener linien": "öffentlicher_verkehr",
        # Employment / public services
        "ams": ["arbeitsamt", "jobcenter", "arbeit"],
        # Other
        "kindergarten": "kindergarten",
        "park": "park",
        "büro": "büro",
        "arbeit": "arbeit",
    },
    Language.EN: {
        "walmart": "supermarket",
        "tesco": "supermarket",
        "sainsbury's": "supermarket",
        "aldi": "supermarket",
        "lidl": "supermarket",
        "kroger": "supermarket",
        "safeway": "supermarket",
        "nhs": "hospital",
        "er": "hospital",
        "pharmacy": "pharmacy",
        "cvs": "pharmacy",
        "walgreens": "pharmacy",
        "school": "school",
        "kindergarten": "kindergarten",
        "office": "office",
        "work": "work",
        "park": "park",
        "station": "station",
        # Employment / public services
        "ams": ["employment office", "job center", "jobcenter", "work"],
        "jobcenter": ["employment office", "job center", "work"],
    },
}


# --- Attendee dictionaries ---
# Family terms, titles, role words → ARASAAC concept word

ATTENDEE_LEXICAL: dict[Language, dict[str, str]] = {
    Language.DE: {
        # Family
        "mami": "mutter",
        "mama": "mutter",
        "mutti": "mutter",
        "mutter": "mutter",
        "papi": "vater",
        "papa": "vater",
        "vati": "vater",
        "vater": "vater",
        "oma": "großmutter",
        "omi": "großmutter",
        "großmutter": "großmutter",
        "opa": "großvater",
        "opi": "großvater",
        "großvater": "großvater",
        "bruder": "bruder",
        "schwester": "schwester",
        "tante": "tante",
        "onkel": "onkel",
        "cousin": "cousin",
        "cousine": "cousine",
        # Titles / roles
        "dr.": "arzt",
        "dr": "arzt",
        "doktor": "arzt",
        "arzt": "arzt",
        "ärztin": "ärztin",
        "lehrer": "lehrer",
        "lehrerin": "lehrerin",
        "freund": "freund",
        "freundin": "freundin",
        "therapeut": "therapeut",
        "therapeutin": "therapeutin",
        "logopäde": "therapeut",
        "logopädin": "therapeutin",
        "psychologe": "psychologe",
        "psychologin": "psychologin",
    },
    Language.EN: {
        "mom": "mother",
        "mum": "mother",
        "mommy": "mother",
        "mother": "mother",
        "dad": "father",
        "daddy": "father",
        "father": "father",
        "grandma": "grandmother",
        "granny": "grandmother",
        "grandmother": "grandmother",
        "grandpa": "grandfather",
        "grandfather": "grandfather",
        "brother": "brother",
        "sister": "sister",
        "aunt": "aunt",
        "uncle": "uncle",
        "cousin": "cousin",
        "dr.": "doctor",
        "dr": "doctor",
        "doctor": "doctor",
        "teacher": "teacher",
        "friend": "friend",
        "therapist": "therapist",
        "psychologist": "psychologist",
        "nurse": "nurse",
    },
}


# --- Generic-fallback concept words per category ---

GENERIC_FALLBACK_CONCEPTS: dict[str, dict[Language, str]] = {
    "summary": {
        Language.DE: "aktivität",
        Language.EN: "activity",
    },
    "location": {
        Language.DE: "ort",
        Language.EN: "place",
    },
}

# Generic person pictogram (user-specified)
GENERIC_PERSON_PICTOGRAM_ID = 34560


def get_location_lexical(text: str, language: Language) -> list[str] | None:
    """Return list of concept-word fallbacks for a location shortcut, else None.

    Always returns a list (even for single-concept entries) so callers can
    iterate uniformly. The first concept that resolves in the index wins.
    """
    val = LOCATION_LEXICAL.get(language, {}).get(text.lower().strip())
    if val is None:
        return None
    if isinstance(val, str):
        return [val]
    return list(val)


def get_attendee_lexical(text: str, language: Language) -> list[str] | None:
    """Return list of concept-word fallbacks for an attendee shortcut, else None."""
    val = ATTENDEE_LEXICAL.get(language, {}).get(text.lower().strip())
    if val is None:
        return None
    if isinstance(val, str):
        return [val]
    return list(val)
