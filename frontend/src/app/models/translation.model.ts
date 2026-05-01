export type Language = 'de' | 'en';

export type MatchType =
  | 'EXACT'
  | 'SLIDING_WINDOW'
  | 'LEXICAL_DICT'
  | 'DISAMBIGUATED'
  | 'PERSONAL_RELATIONSHIP'
  | 'LEMMA'
  | 'COMPOUND_SPLIT'
  | 'SYNSET'
  | 'HYPERNYM'
  | 'NER_PERSON_FALLBACK'
  | 'GENERIC_FALLBACK';

export interface TranslationRequest {
  summary: string;
  location: string;
  attendees: string;
  language: Language;
}

export interface Keyword {
  type?: number;
  keyword?: string;
  hasLocution?: boolean;
  plural?: string;
}

export interface PictogramMatch {
  pictogramId: number;
  imageUrl: string;
  matchedTerm: string;
  originalInput: string;
  matchType: MatchType;
  confidence: number;
  keywords: Keyword[];
}

export interface FieldTranslation {
  originalText: string;
  matches: PictogramMatch[];
  unmatchedTokens: string[];
}

export interface AttendeeTranslation {
  originalAttendee: string;
  matches: PictogramMatch[];
  unmatchedTokens: string[];
}

export interface TranslationResponse {
  language: Language;
  summary: FieldTranslation;
  location: FieldTranslation;
  attendees: AttendeeTranslation[];
}

// --- Evaluation models ---

export interface EvaluationMetrics {
  total_entries: number;
  coverage_summary: number;
  coverage_location: number;
  coverage_attendees: number;
  accuracy_summary: number;
  accuracy_location: number;
  accuracy_attendees: number;
  accuracy_overall: number;
  precision_summary: number;
  recall_summary: number;
  f1_summary: number;
  precision_location: number;
  recall_location: number;
  f1_location: number;
  precision_attendees: number;
  recall_attendees: number;
  f1_attendees: number;
  precision_macro: number;
  recall_macro: number;
  f1_macro: number;
  pp_precision_summary: number;
  pp_recall_summary: number;
  pp_f1_summary: number;
  pp_precision_location: number;
  pp_recall_location: number;
  pp_f1_location: number;
  pp_precision_attendees: number;
  pp_recall_attendees: number;
  pp_f1_attendees: number;
  pp_precision_macro: number;
  pp_recall_macro: number;
  pp_f1_macro: number;
  avg_confidence: number;
  match_type_distribution: Record<string, number>;
  avg_unmatched_tokens_per_entry: number;
}

export interface EvaluationEntry {
  id: string;
  language: Language;
  summary: string;
  location: string;
  attendees: string;
  // OR-groups: each inner array is one slot; the prediction must contain
  // at least one ID from each slot.
  expected_summary: number[][];
  expected_location: number[][];
  expected_attendees: number[][];
  response: TranslationResponse;
  summary_correct: boolean | null;
  location_correct: boolean | null;
  attendees_correct: boolean | null;
}

export interface EvaluationRun {
  run_id: string;
  language: Language;
  timestamp: string;
  metrics: EvaluationMetrics;
  entries: EvaluationEntry[];
}

export interface EvaluationRunSummary {
  run_id: string;
  language: Language;
  timestamp: string;
  filename: string;
  total_entries: number;
}
