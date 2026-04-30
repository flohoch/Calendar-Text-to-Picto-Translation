"""
Builds and holds per-language in-memory indices over the ARASAAC pictogram
database for fast multi-strategy lookups.

Indices per language:
- exact_index:        lowercased term → list of Pictograms
- lemma_index:        spaCy-lemmatized keyword → list of Pictograms
- synset_index:       ARASAAC synset ID → list of Pictograms
- keyword_to_synsets: lowercased keyword → set of synset IDs
- vocabulary:         set of all lowercased keywords (for compound splitter)
"""
from __future__ import annotations

import logging
from collections import defaultdict

from app.models.schemas import Language, Pictogram
from app.services import compound_splitter, nlp_service
from app.services.database import get_db

logger = logging.getLogger(__name__)


# Per-language storage
exact_index: dict[Language, dict[str, list[Pictogram]]] = {
    Language.DE: defaultdict(list),
    Language.EN: defaultdict(list),
}
lemma_index: dict[Language, dict[str, list[Pictogram]]] = {
    Language.DE: defaultdict(list),
    Language.EN: defaultdict(list),
}
synset_index: dict[Language, dict[str, list[Pictogram]]] = {
    Language.DE: defaultdict(list),
    Language.EN: defaultdict(list),
}
keyword_to_synsets: dict[Language, dict[str, set[str]]] = {
    Language.DE: defaultdict(set),
    Language.EN: defaultdict(set),
}
vocabulary: dict[Language, set[str]] = {Language.DE: set(), Language.EN: set()}

total_pictograms: dict[Language, int] = {Language.DE: 0, Language.EN: 0}


_COLLECTION_NAMES = {Language.DE: "pictograms_de", Language.EN: "pictograms_en"}


def collection_name(language: Language) -> str:
    return _COLLECTION_NAMES[language]


def build_indices() -> None:
    """Load pictograms from MongoDB and build the indices for every language."""
    db = get_db()
    for language in (Language.DE, Language.EN):
        coll_name = _COLLECTION_NAMES[language]
        if coll_name not in db.list_collection_names():
            logger.warning("Collection '%s' not found, skipping %s indices.",
                           coll_name, language.value)
            continue
        _build_for_language(language, coll_name)

    # Provide vocabulary to the German compound splitter
    if vocabulary[Language.DE]:
        compound_splitter.set_vocabulary(vocabulary[Language.DE])


def _build_for_language(language: Language, coll_name: str) -> None:
    db = get_db()
    cursor = db[coll_name].find()

    indexed = 0
    total = 0
    for doc in cursor:
        total += 1
        try:
            p = Pictogram.model_validate(doc)
            _index_single(p, language)
            indexed += 1
        except Exception as e:
            logger.warning("Failed to index pictogram %s (%s): %s",
                           doc.get("_id"), language.value, e)

    total_pictograms[language] = total
    logger.info(
        "[%s] Indexed %d/%d pictograms — exact:%d lemma:%d synset:%d vocab:%d",
        language.value, indexed, total,
        len(exact_index[language]),
        len(lemma_index[language]),
        len(synset_index[language]),
        len(vocabulary[language]),
    )


def _index_single(p: Pictogram, language: Language) -> None:
    # Exact: from pre-computed searchTerms (keywords + plurals + tags + categories)
    for term in p.search_terms:
        if term and term.strip():
            exact_index[language][term].append(p)
            vocabulary[language].add(term)

    # Lemma index — lemmatize each keyword via spaCy
    for kw in p.keywords:
        keyword = kw.keyword
        if not keyword or not keyword.strip():
            continue
        lower = keyword.strip().lower()

        # Map keyword → synsets
        if p.synsets:
            keyword_to_synsets[language][lower].update(p.synsets)

        # Lemma indexing per word in the keyword
        try:
            for word in lower.split():
                lemma = nlp_service.lemma(word, language)
                if lemma and lemma.strip():
                    lemma_index[language][lemma].append(p)
                    vocabulary[language].add(lemma)
        except Exception as e:
            logger.debug("Lemma indexing failed for '%s' (%s): %s", lower, language.value, e)

        # Plural lemma
        plural = kw.plural
        if plural and plural.strip():
            try:
                plural_lemma = nlp_service.lemma(plural.strip().lower(), language)
                lemma_index[language][plural_lemma].append(p)
            except Exception:
                pass

    # Synset index
    for synset_id in p.synsets:
        if synset_id and synset_id.strip():
            synset_index[language][synset_id].append(p)


# --- Query API ---


def find_by_exact(term: str, language: Language) -> list[Pictogram]:
    return exact_index[language].get(term, [])


def find_by_lemma(lemma: str, language: Language) -> list[Pictogram]:
    return lemma_index[language].get(lemma, [])


def find_by_synset(synset_id: str, language: Language) -> list[Pictogram]:
    return synset_index[language].get(synset_id, [])


def get_synsets_for_keyword(keyword: str, language: Language) -> set[str]:
    return keyword_to_synsets[language].get(keyword, set())


def find_by_any_synset(synset_ids: set[str], language: Language) -> list[Pictogram]:
    results: list[Pictogram] = []
    seen: set[int] = set()
    for sid in synset_ids:
        for p in find_by_synset(sid, language):
            if p.id not in seen:
                seen.add(p.id)
                results.append(p)
    return results


def get_vocabulary(language: Language) -> set[str]:
    return vocabulary[language]


def get_total(language: Language) -> int:
    return total_pictograms[language]


def get_pictogram_by_id(pictogram_id: int, language: Language) -> Pictogram | None:
    db = get_db()
    doc = db[_COLLECTION_NAMES[language]].find_one({"_id": pictogram_id})
    if doc is None:
        return None
    try:
        return Pictogram.model_validate(doc)
    except Exception:
        return None
