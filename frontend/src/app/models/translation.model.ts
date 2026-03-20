export interface TranslationRequest {
  summary: string;
  location: string;
  participants: string;
}

export interface Keyword {
  type: number;
  keyword: string;
  hasLocution: boolean;
  plural: string;
}

export interface PictogramMatch {
  matchedTerm: string;
  pictogramId: number;
  imageUrl: string;
  keywords: Keyword[];
  matchType: 'EXACT' | 'STEMMED' | 'SYNSET';
}

export interface FieldTranslation {
  originalText: string;
  matches: PictogramMatch[];
  unmatchedTokens: string[];
}

export interface TranslationResponse {
  summary: FieldTranslation;
  location: FieldTranslation;
  participants: FieldTranslation;
}
