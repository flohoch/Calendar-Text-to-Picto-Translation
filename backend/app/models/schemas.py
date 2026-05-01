"""Pydantic models for API contracts and internal data structures."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Language(str, Enum):
    DE = "de"
    EN = "en"


class MatchType(str, Enum):
    EXACT = "EXACT"
    SLIDING_WINDOW = "SLIDING_WINDOW"
    LEXICAL_DICT = "LEXICAL_DICT"
    DISAMBIGUATED = "DISAMBIGUATED"
    PERSONAL_RELATIONSHIP = "PERSONAL_RELATIONSHIP"
    LEMMA = "LEMMA"
    COMPOUND_SPLIT = "COMPOUND_SPLIT"
    SYNSET = "SYNSET"
    HYPERNYM = "HYPERNYM"
    NER_PERSON_FALLBACK = "NER_PERSON_FALLBACK"
    GENERIC_FALLBACK = "GENERIC_FALLBACK"


# Confidence values per match strategy
CONFIDENCE_BY_TYPE: dict[MatchType, float] = {
    MatchType.SLIDING_WINDOW: 1.0,           # most specific (multi-word)
    MatchType.EXACT: 0.95,                    # single-token exact match
    MatchType.PERSONAL_RELATIONSHIP: 0.95,
    MatchType.LEXICAL_DICT: 0.9,
    MatchType.DISAMBIGUATED: 0.85,
    MatchType.LEMMA: 0.8,
    MatchType.COMPOUND_SPLIT: 0.7,
    MatchType.SYNSET: 0.7,
    MatchType.HYPERNYM: 0.55,
    MatchType.NER_PERSON_FALLBACK: 0.5,
    MatchType.GENERIC_FALLBACK: 0.3,
}


# --- Request / Response DTOs ---


class TranslationRequest(BaseModel):
    summary: str = ""
    location: str = ""
    attendees: str = ""  # comma-separated list of attendees
    language: Language = Language.DE


class Keyword(BaseModel):
    type: Optional[int] = None
    keyword: Optional[str] = None
    has_locution: Optional[bool] = Field(None, alias="hasLocution")
    plural: Optional[str] = None

    model_config = {"populate_by_name": True}


class PictogramMatch(BaseModel):
    pictogram_id: int = Field(alias="pictogramId")
    image_url: str = Field(alias="imageUrl")
    matched_term: str = Field(alias="matchedTerm")
    original_input: str = Field(alias="originalInput")
    match_type: MatchType = Field(alias="matchType")
    confidence: float
    keywords: list[Keyword] = []

    model_config = {"populate_by_name": True}


class FieldTranslation(BaseModel):
    """Result for SUMMARY or LOCATION field."""
    original_text: str = Field(alias="originalText")
    matches: list[PictogramMatch] = []
    unmatched_tokens: list[str] = Field(default_factory=list, alias="unmatchedTokens")

    model_config = {"populate_by_name": True}


class AttendeeTranslation(BaseModel):
    """Result for a single attendee (comma-separated)."""
    original_attendee: str = Field(alias="originalAttendee")
    matches: list[PictogramMatch] = []
    unmatched_tokens: list[str] = Field(default_factory=list, alias="unmatchedTokens")

    model_config = {"populate_by_name": True}


class TranslationResponse(BaseModel):
    language: Language
    summary: FieldTranslation
    location: FieldTranslation
    attendees: list[AttendeeTranslation]


# --- Evaluation models ---


class EvaluationEntry(BaseModel):
    """One row of evaluation output."""
    id: str
    language: Language
    summary: str
    location: str
    attendees: str
    # Targets: list of OR-groups. Each group is a list of acceptable IDs;
    # the prediction must contain at least one ID from EACH group.
    # Format in CSV: "[id,id,...]"  or  "[id,id],[id,id]"  for sequences.
    expected_summary: list[list[int]] = []
    expected_location: list[list[int]] = []
    expected_attendees: list[list[int]] = []
    response: TranslationResponse
    summary_correct: Optional[bool] = None
    location_correct: Optional[bool] = None
    attendees_correct: Optional[bool] = None


class EvaluationMetrics(BaseModel):
    """Aggregate metrics over an evaluation run."""
    total_entries: int
    coverage_summary: float           # % entries with at least one summary match
    coverage_location: float
    coverage_attendees: float
    accuracy_summary: float           # % where every target group has a hit
    accuracy_location: float
    accuracy_attendees: float
    accuracy_overall: float           # % where all three fields are correct

    # --- Slot-based P/R/F1 ---
    # Recall = covered slots / total slots (= accuracy at slot granularity).
    # Precision = predictions that hit any slot / total predictions.
    # F1 = harmonic mean.
    precision_summary: float
    recall_summary: float
    f1_summary: float
    precision_location: float
    recall_location: float
    f1_location: float
    precision_attendees: float
    recall_attendees: float
    f1_attendees: float
    precision_macro: float
    recall_macro: float
    f1_macro: float

    # --- Per-prediction (set-based) P/R/F1 ---
    # Targets treated as a flat union of all slot IDs; predictions treated as a flat set.
    # Stricter than slot-based Recall: every target ID must be predicted, alternatives
    # within a slot don't grant credit to each other.
    pp_precision_summary: float
    pp_recall_summary: float
    pp_f1_summary: float
    pp_precision_location: float
    pp_recall_location: float
    pp_f1_location: float
    pp_precision_attendees: float
    pp_recall_attendees: float
    pp_f1_attendees: float
    pp_precision_macro: float
    pp_recall_macro: float
    pp_f1_macro: float

    avg_confidence: float
    match_type_distribution: dict[str, int]
    avg_unmatched_tokens_per_entry: float


class EvaluationRun(BaseModel):
    run_id: str
    language: Language
    timestamp: str
    metrics: EvaluationMetrics
    entries: list[EvaluationEntry]


# --- MongoDB document ---


class Pictogram(BaseModel):
    """Mirrors the MongoDB document structure."""
    id: int = Field(alias="_id")
    schematic: Optional[bool] = None
    sex: Optional[bool] = None
    violence: Optional[bool] = None
    aac: Optional[bool] = None
    aac_color: Optional[bool] = Field(None, alias="aacColor")
    skin: Optional[bool] = None
    hair: Optional[bool] = None
    downloads: Optional[int] = None
    categories: list[str] = []
    synsets: list[str] = []
    tags: list[str] = []
    keywords: list[Keyword] = []
    search_terms: list[str] = Field(default_factory=list, alias="searchTerms")

    model_config = {"populate_by_name": True}

    def to_match(self, original_input: str, matched_term: str,
                 match_type: MatchType, confidence: Optional[float] = None) -> PictogramMatch:
        if confidence is None:
            confidence = CONFIDENCE_BY_TYPE.get(match_type, 0.5)
        image_url = f"https://static.arasaac.org/pictograms/{self.id}/{self.id}_500.png"
        return PictogramMatch(
            pictogramId=self.id,
            imageUrl=image_url,
            matchedTerm=matched_term,
            originalInput=original_input,
            matchType=match_type,
            confidence=round(confidence, 3),
            keywords=self.keywords,
        )
