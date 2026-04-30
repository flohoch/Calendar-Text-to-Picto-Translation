"""
NLP service wrapping spaCy pipelines for German and English.
Provides POS tagging, lemmatization, and NER.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import spacy
from spacy.language import Language as SpacyLanguage

from app.models.schemas import Language

logger = logging.getLogger(__name__)


@dataclass
class Token:
    text: str
    lemma: str
    pos: str
    is_stop: bool
    is_punct: bool
    is_alpha: bool


@dataclass
class Entity:
    text: str
    label: str  # e.g. "PER", "ORG", "LOC"
    start: int
    end: int


@dataclass
class NlpResult:
    text: str
    tokens: list[Token]
    entities: list[Entity]

    def content_tokens(self) -> list[Token]:
        """Return non-stop, non-punct, alphabetic tokens."""
        return [t for t in self.tokens if not t.is_punct and t.is_alpha]


_pipelines: dict[Language, SpacyLanguage] = {}


def init() -> None:
    """Load spaCy models for both languages."""
    global _pipelines
    try:
        logger.info("Loading spaCy model: de_core_news_md")
        _pipelines[Language.DE] = spacy.load("de_core_news_md")
        logger.info("Loading spaCy model: en_core_web_md")
        _pipelines[Language.EN] = spacy.load("en_core_web_md")
        logger.info("spaCy models loaded.")
    except OSError as e:
        logger.error("Failed to load spaCy models: %s", e)
        raise


def process(text: str, language: Language) -> NlpResult:
    """Run the spaCy pipeline on text and return tokens + entities."""
    if not text or not text.strip():
        return NlpResult(text=text, tokens=[], entities=[])

    nlp = _pipelines.get(language)
    if nlp is None:
        raise RuntimeError(f"spaCy pipeline for {language} not initialized")

    doc = nlp(text)
    tokens = [
        Token(
            text=tok.text,
            lemma=tok.lemma_.lower() if tok.lemma_ else tok.text.lower(),
            pos=tok.pos_,
            is_stop=tok.is_stop,
            is_punct=tok.is_punct,
            is_alpha=tok.is_alpha,
        )
        for tok in doc
    ]
    entities = [
        Entity(text=ent.text, label=ent.label_, start=ent.start_char, end=ent.end_char)
        for ent in doc.ents
    ]
    return NlpResult(text=text, tokens=tokens, entities=entities)


def lemma(word: str, language: Language) -> str:
    """Convenience: get lemma for a single word."""
    result = process(word, language)
    if result.tokens:
        return result.tokens[0].lemma
    return word.lower()
