"""WordNet-based synset operations using NLTK."""
from __future__ import annotations

import logging
from typing import Optional

from nltk.corpus import wordnet as wn

logger = logging.getLogger(__name__)

_POS_MAP = {"n": wn.NOUN, "v": wn.VERB, "a": wn.ADJ, "r": wn.ADV}
_POS_REVERSE = {v: k for k, v in _POS_MAP.items()}

_available = False


def init() -> None:
    global _available
    try:
        import nltk
        nltk.download("wordnet", quiet=True)
        nltk.download("omw-1.4", quiet=True)
        wn.synsets("dog")
        _available = True
        logger.info("WordNet loaded successfully.")
    except Exception as e:
        logger.warning("WordNet init failed: %s", e)
        _available = False


def is_available() -> bool:
    return _available


def resolve(arasaac_synset_id: str):
    if not _available or not arasaac_synset_id or len(arasaac_synset_id) < 3:
        return None
    try:
        dash_idx = arasaac_synset_id.rfind("-")
        if dash_idx < 1:
            return None
        offset = int(arasaac_synset_id[:dash_idx])
        pos_char = arasaac_synset_id[dash_idx + 1]
        pos = _POS_MAP.get(pos_char)
        if pos is None:
            return None
        return wn.synset_from_pos_and_offset(pos, offset)
    except Exception:
        return None


def to_arasaac_format(synset) -> Optional[str]:
    if synset is None:
        return None
    pos_char = _POS_REVERSE.get(synset.pos())
    if pos_char is None:
        return None
    return f"{synset.offset():08d}-{pos_char}"


def get_hypernyms(arasaac_synset_id: str, max_depth: int = 2) -> list[set[str]]:
    """
    Return hypernyms grouped by depth level: [depth_1_set, depth_2_set, ...]
    """
    levels: list[set[str]] = []
    if not _available:
        return levels

    synset = resolve(arasaac_synset_id)
    if synset is None:
        return levels

    current_level = {synset}
    seen: set[str] = {arasaac_synset_id}

    for _ in range(max_depth):
        next_level: set = set()
        next_ids: set[str] = set()
        for s in current_level:
            try:
                for h in s.hypernyms():
                    h_id = to_arasaac_format(h)
                    if h_id and h_id not in seen:
                        next_level.add(h)
                        next_ids.add(h_id)
                        seen.add(h_id)
            except Exception:
                continue
        if not next_level:
            break
        levels.append(next_ids)
        current_level = next_level

    return levels


def get_hypernyms_for_all(synset_ids: set[str], max_depth: int = 2) -> list[set[str]]:
    """Aggregate hypernyms by depth across multiple starting synsets."""
    aggregated: list[set[str]] = [set() for _ in range(max_depth)]
    for sid in synset_ids:
        levels = get_hypernyms(sid, max_depth)
        for i, level in enumerate(levels):
            if i < max_depth:
                aggregated[i].update(level)
    return aggregated


def lookup_synsets_for_word(word: str, language: str | None = None) -> set[str]:
    """
    Look up a word directly in WordNet. For English (or `language` not given),
    uses NLTK WordNet's default English vocabulary. For German (`language='de'`),
    uses Open Multilingual WordNet's German index (`lang='deu'`).

    Returns ARASAAC-format synset IDs for every synset the word participates
    in. Use this when the word is NOT an ARASAAC keyword and therefore has
    no entry in keyword-to-synsets, but might still resolve through
    direct WordNet membership.
    """
    if not _available or not word or not word.strip():
        return set()

    result: set[str] = set()
    word_lower = word.strip().lower()

    # Map our Language enum value to NLTK's OMW language code.
    omw_lang = None
    if language == "de":
        omw_lang = "deu"
    elif language == "en":
        omw_lang = None  # default English

    try:
        if omw_lang:
            synsets = wn.synsets(word_lower, lang=omw_lang)
        else:
            synsets = wn.synsets(word_lower)
        for s in synsets:
            sid = to_arasaac_format(s)
            if sid:
                result.add(sid)
    except Exception as e:
        logger.debug("WordNet lookup failed for '%s' (lang=%s): %s",
                     word, language, e)

    # Fallback: if German lookup found nothing AND the word might also exist
    # in English WordNet, try the English index too. Cheap belt-and-suspenders.
    if not result and omw_lang:
        try:
            synsets = wn.synsets(word_lower)
            for s in synsets:
                sid = to_arasaac_format(s)
                if sid:
                    result.add(sid)
        except Exception:
            pass

    return result
