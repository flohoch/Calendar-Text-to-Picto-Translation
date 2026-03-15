package com.pictogramtranslator.model;

public class Keyword {

    private Integer type;
    private String keyword;
    private Boolean hasLocution;
    private String plural;

    public Keyword() {}

    public Integer getType() { return type; }
    public void setType(Integer type) { this.type = type; }

    public String getKeyword() { return keyword; }
    public void setKeyword(String keyword) { this.keyword = keyword; }

    public Boolean getHasLocution() { return hasLocution; }
    public void setHasLocution(Boolean hasLocution) { this.hasLocution = hasLocution; }

    public String getPlural() { return plural; }
    public void setPlural(String plural) { this.plural = plural; }
}