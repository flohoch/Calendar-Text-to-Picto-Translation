package com.pictogramtranslator.model;

public class Keyword {

    private int type;
    private String keyword;
    private boolean hasLocution;
    private String plural;

    public Keyword() {}

    public int getType() { return type; }
    public void setType(int type) { this.type = type; }

    public String getKeyword() { return keyword; }
    public void setKeyword(String keyword) { this.keyword = keyword; }

    public boolean isHasLocution() { return hasLocution; }
    public void setHasLocution(boolean hasLocution) { this.hasLocution = hasLocution; }

    public String getPlural() { return plural; }
    public void setPlural(String plural) { this.plural = plural; }
}
