package com.pictogramtranslator.model;

import java.util.List;

public class PictogramMatch {

    /**
     * Describes how the pictogram was matched.
     */
    public enum MatchType {
        /** Exact keyword match (single or multi-word). */
        EXACT,
        /** Matched after stemming the input token. */
        STEMMED,
        /** Matched via WordNet synset / hypernym traversal. */
        SYNSET
    }

    private String matchedTerm;
    private int pictogramId;
    private String imageUrl;
    private List<Keyword> keywords;
    private MatchType matchType;

    public PictogramMatch() {}

    public PictogramMatch(String matchedTerm, Pictogram pictogram, MatchType matchType) {
        this.matchedTerm = matchedTerm;
        this.pictogramId = pictogram.getId();
        this.imageUrl = String.format(
                "https://static.arasaac.org/pictograms/%d/%d_500.png",
                pictogram.getId(), pictogram.getId());
        this.keywords = pictogram.getKeywords();
        this.matchType = matchType;
    }

    public String getMatchedTerm() { return matchedTerm; }
    public void setMatchedTerm(String matchedTerm) { this.matchedTerm = matchedTerm; }

    public int getPictogramId() { return pictogramId; }
    public void setPictogramId(int pictogramId) { this.pictogramId = pictogramId; }

    public String getImageUrl() { return imageUrl; }
    public void setImageUrl(String imageUrl) { this.imageUrl = imageUrl; }

    public List<Keyword> getKeywords() { return keywords; }
    public void setKeywords(List<Keyword> keywords) { this.keywords = keywords; }

    public MatchType getMatchType() { return matchType; }
    public void setMatchType(MatchType matchType) { this.matchType = matchType; }
}
