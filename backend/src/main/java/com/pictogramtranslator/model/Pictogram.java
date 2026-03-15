package com.pictogramtranslator.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;

import java.time.Instant;
import java.util.List;

@Document(collection = "pictograms")
public class Pictogram {

    @Id
    @Field("_id")
    private int id;

    private Boolean schematic;
    private Boolean sex;
    private Boolean violence;
    private Boolean aac;
    private Boolean aacColor;
    private Boolean skin;
    private Boolean hair;
    private Integer downloads;

    private List<String> categories;
    private List<String> synsets;
    private List<String> tags;
    private List<Keyword> keywords;

    /** Lowercased terms added by the data-loader for fast exact matching. */
    private List<String> searchTerms;

    private Instant created;
    private Instant lastUpdated;

    public Pictogram() {}

    // --- Getters and Setters ---

    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public Boolean isSchematic() { return schematic; }
    public void setSchematic(Boolean schematic) { this.schematic = schematic; }

    public Boolean isSex() { return sex; }
    public void setSex(Boolean sex) { this.sex = sex; }

    public Boolean isViolence() { return violence; }
    public void setViolence(Boolean violence) { this.violence = violence; }

    public Boolean isAac() { return aac; }
    public void setAac(Boolean aac) { this.aac = aac; }

    public Boolean isAacColor() { return aacColor; }
    public void setAacColor(Boolean aacColor) { this.aacColor = aacColor; }

    public Boolean isSkin() { return skin; }
    public void setSkin(Boolean skin) { this.skin = skin; }

    public Boolean isHair() { return hair; }
    public void setHair(Boolean hair) { this.hair = hair; }

    public Integer getDownloads() { return downloads; }
    public void setDownloads(Integer downloads) { this.downloads = downloads; }

    public List<String> getCategories() { return categories; }
    public void setCategories(List<String> categories) { this.categories = categories; }

    public List<String> getSynsets() { return synsets; }
    public void setSynsets(List<String> synsets) { this.synsets = synsets; }

    public List<String> getTags() { return tags; }
    public void setTags(List<String> tags) { this.tags = tags; }

    public List<Keyword> getKeywords() { return keywords; }
    public void setKeywords(List<Keyword> keywords) { this.keywords = keywords; }

    public List<String> getSearchTerms() { return searchTerms; }
    public void setSearchTerms(List<String> searchTerms) { this.searchTerms = searchTerms; }

    public Instant getCreated() { return created; }
    public void setCreated(Instant created) { this.created = created; }

    public Instant getLastUpdated() { return lastUpdated; }
    public void setLastUpdated(Instant lastUpdated) { this.lastUpdated = lastUpdated; }
}
