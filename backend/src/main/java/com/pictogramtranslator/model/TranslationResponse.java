package com.pictogramtranslator.model;

import java.util.List;

public class TranslationResponse {

    private FieldTranslation summary;
    private FieldTranslation location;
    private FieldTranslation participants;

    public TranslationResponse() {}

    public TranslationResponse(FieldTranslation summary, FieldTranslation location,
                               FieldTranslation participants) {
        this.summary = summary;
        this.location = location;
        this.participants = participants;
    }

    public FieldTranslation getSummary() { return summary; }
    public void setSummary(FieldTranslation summary) { this.summary = summary; }

    public FieldTranslation getLocation() { return location; }
    public void setLocation(FieldTranslation location) { this.location = location; }

    public FieldTranslation getParticipants() { return participants; }
    public void setParticipants(FieldTranslation participants) { this.participants = participants; }

    public static class FieldTranslation {

        private String originalText;
        private List<PictogramMatch> matches;
        private List<String> unmatchedTokens;

        public FieldTranslation() {}

        public FieldTranslation(String originalText, List<PictogramMatch> matches,
                                List<String> unmatchedTokens) {
            this.originalText = originalText;
            this.matches = matches;
            this.unmatchedTokens = unmatchedTokens;
        }

        public String getOriginalText() { return originalText; }
        public void setOriginalText(String originalText) { this.originalText = originalText; }

        public List<PictogramMatch> getMatches() { return matches; }
        public void setMatches(List<PictogramMatch> matches) { this.matches = matches; }

        public List<String> getUnmatchedTokens() { return unmatchedTokens; }
        public void setUnmatchedTokens(List<String> unmatchedTokens) { this.unmatchedTokens = unmatchedTokens; }
    }
}
