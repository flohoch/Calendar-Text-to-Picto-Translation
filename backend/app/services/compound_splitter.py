"""
German compound splitter.

Strategy (in order):
1. If the word IS in the ARASAAC vocabulary → no split.
2. Greedy longest-prefix split — accepts only when BOTH parts are in the
   vocabulary (no recursion), and rejects single-character or short parts.
3. Fall back to the `compound_split` library (CharSplit-based statistical
   model) — also requires both parts to be in the vocabulary.

A split is only accepted if every produced part matches an ARASAAC keyword.
This prevents pathological splits like "Lesenachhilfe" → "lesenach" + "hilfe"
(where "lesenach" is incidentally in the vocab but is the wrong split point)
or "Töpferklasse" → "töferk" + "laß" (nonsense parts).

If no valid split is found, returns [word] — leaving the original to be
matched (or not) by the standard pipeline tiers.
"""
from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)

_lib_split: Callable[[str], list[str]] | None = None
try:
    from compound_split import char_split

    def _lib_split_fn(word: str) -> list[str]:
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


_vocabulary: set[str] = set()
MIN_PART_LEN = 4


def set_vocabulary(words: set[str]) -> None:
    global _vocabulary
    _vocabulary = {w for w in words if w and len(w) >= MIN_PART_LEN}
    logger.info("Compound splitter vocabulary set: %d entries.", len(_vocabulary))


def split(word: str) -> list[str]:
    """
    Split a German compound. Returns [word.lower()] if no valid split is
    found, or the parts (each lowercased) if every part is in the vocabulary.
    """
    if not word:
        return [word]

    lower = word.lower()

    # Tier 1: word itself is a vocabulary entry
    if lower in _vocabulary:
        return [lower]

    # Tier 2: greedy split (both parts must be in vocab)
    parts = _greedy_two_part_split(lower)
    if parts:
        logger.debug("Greedy compound split: '%s' → %s", word, parts)
        return parts

    # Tier 3: library split (both parts must be in vocab)
    if _lib_split is not None:
        lib_parts = _lib_split(word)
        if lib_parts and len(lib_parts) == 2 and _all_in_vocab(lib_parts):
            logger.debug("Library compound split: '%s' → %s", word, lib_parts)
            return lib_parts

    return [lower]


def _all_in_vocab(parts: list[str]) -> bool:
    return all(len(p) >= MIN_PART_LEN and p in _vocabulary for p in parts)


def _greedy_two_part_split(word: str) -> list[str] | None:
    """
    Try to split `word` into exactly two parts where BOTH parts are in
    the vocabulary. Prefers longer prefixes. Handles the German linking
    morpheme '-s-' between parts.

    Returns a list of two parts on success, or None.
    """
    if not _vocabulary:
        return None

    n = len(word)
    if n < MIN_PART_LEN * 2:
        return None

    # Iterate from longest prefix to shortest, requiring BOTH halves valid
    for prefix_len in range(n - MIN_PART_LEN, MIN_PART_LEN - 1, -1):
        prefix = word[:prefix_len]
        if prefix not in _vocabulary:
            continue

        remainder = word[prefix_len:]

        # Direct match
        if len(remainder) >= MIN_PART_LEN and remainder in _vocabulary:
            return [prefix, remainder]

        # Strip linking 's' or 'es'
        for skip in (1, 2):
            if (remainder.startswith("s" if skip == 1 else "es")
                    and len(remainder) - skip >= MIN_PART_LEN):
                stripped = remainder[skip:]
                if stripped in _vocabulary:
                    return [prefix, stripped]

    # Nothing produced a valid two-part split
    return None
