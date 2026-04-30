"""
Hand-curated lexical dictionaries that map common shortcuts/brand names to
ARASAAC-relevant concept words. Concepts are looked up in the pictogram
index, so we don't hardcode pictogram IDs (which makes this robust to
ARASAAC database changes).
"""
from app.models.schemas import Language


# --- Location dictionaries ---
# Brand names / abbreviations → ARASAAC concept word

LOCATION_LEXICAL: dict[Language, dict[str, str]] = {
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
GENERIC_PERSON_PICTOGRAM_ID = 36935


def get_location_lexical(text: str, language: Language) -> str | None:
    """Return concept word if text matches a location shortcut, else None."""
    return LOCATION_LEXICAL.get(language, {}).get(text.lower().strip())


def get_attendee_lexical(text: str, language: Language) -> str | None:
    """Return concept word if text matches an attendee shortcut, else None."""
    return ATTENDEE_LEXICAL.get(language, {}).get(text.lower().strip())
