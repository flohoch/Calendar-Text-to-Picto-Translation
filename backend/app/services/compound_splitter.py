"""
German compound splitter.

Two-stage strategy:
1. Try the `compound_split` library (CharSplit-based) for statistical splitting.
2. Fall back to greedy ARASAAC-keyword-based splitting that grounds splits
   in our actual pictogram vocabulary.

Examples:
    "Zahnarzttermin" → ["zahn", "arzt", "termin"]
    "Frühstückstisch" → ["frühstück", "tisch"]
"""
from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)

_lib_split: Callable[[str], list[str]] | None = None
try:
    from compound_split import char_split

    def _lib_split_fn(word: str) -> list[str]:
        # char_split returns list of (probability, head, tail). Take best split.
        try:
            results = char_split.split_compound(word)
            if results:
                _, head, tail = results[0]
                if head and tail:
                    return [head.lower(), tail.lower()]
        except Exception:
            pass
        return []

    _lib_split = _lib_split_fn
    logger.info("compound_split library available for German compound splitting.")
except ImportError:
    logger.warning("compound_split not installed — falling back to greedy splitter only.")


# Set populated at startup with ARASAAC keyword vocabulary
_vocabulary: set[str] = set()
MIN_PART_LEN = 3


def set_vocabulary(words: set[str]) -> None:
    """Provide the lowercased ARASAAC keyword set used for greedy splitting."""
    global _vocabulary
    _vocabulary = {w for w in words if w and len(w) >= MIN_PART_LEN}
    logger.info("Compound splitter vocabulary set: %d entries.", len(_vocabulary))


def split(word: str) -> list[str]:
    """
    Split a German compound. Returns at least [word.lower()] (the input itself).
    If the word is splittable, returns the parts (each lowercased).
    """
    if not word:
        return [word]

    lower = word.lower()

    # Tier 1: Greedy ARASAAC-vocabulary split
    parts = _greedy_split(lower)
    if parts and len(parts) > 1:
        logger.debug("Greedy compound split: '%s' → %s", word, parts)
        return parts

    # Tier 2: Library split
    if _lib_split is not None:
        lib_parts = _lib_split(word)
        if lib_parts and len(lib_parts) > 1:
            logger.debug("Library compound split: '%s' → %s", word, lib_parts)
            return lib_parts

    return [lower]


def _greedy_split(word: str) -> list[str]:
    """
    Greedy longest-prefix split using the ARASAAC vocabulary as a dictionary.
    Returns parts only if the entire word can be segmented.
    """
    if not _vocabulary:
        return [word]

    n = len(word)
    if n < MIN_PART_LEN * 2:
        return [word]

    # Find longest prefix that's in vocabulary
    for prefix_len in range(n - MIN_PART_LEN, MIN_PART_LEN - 1, -1):
        prefix = word[:prefix_len]
        if prefix in _vocabulary:
            remainder = word[prefix_len:]
            # Strip German linking morpheme 's'
            if remainder.startswith("s") and len(remainder) > MIN_PART_LEN:
                remainder_stripped = remainder[1:]
                if remainder_stripped in _vocabulary:
                    return [prefix, remainder_stripped]
                # try recursing on stripped remainder
                rest_parts = _greedy_split(remainder_stripped)
                if len(rest_parts) > 1 or remainder_stripped in _vocabulary:
                    return [prefix] + rest_parts
            if remainder in _vocabulary:
                return [prefix, remainder]
            # Recurse on remainder
            rest_parts = _greedy_split(remainder)
            if len(rest_parts) > 1:
                return [prefix] + rest_parts

    return [word]
