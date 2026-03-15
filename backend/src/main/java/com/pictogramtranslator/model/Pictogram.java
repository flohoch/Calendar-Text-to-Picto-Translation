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

    private boolean schematic;
    private boolean sex;
    private boolean violence;
    private boolean aac;
    private boolean aacColor;
    private boolean skin;
    private boolean hair;
    private int downloads;

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

    public boolean isSchematic() { return schematic; }
    public void setSchematic(boolean schematic) { this.schematic = schematic; }

    public boolean isSex() { return sex; }
    public void setSex(boolean sex) { this.sex = sex; }

    public boolean isViolence() { return violence; }
    public void setViolence(boolean violence) { this.violence = violence; }

    public boolean isAac() { return aac; }
    public void setAac(boolean aac) { this.aac = aac; }

    public boolean isAacColor() { return aacColor; }
    public void setAacColor(boolean aacColor) { this.aacColor = aacColor; }

    public boolean isSkin() { return skin; }
    public void setSkin(boolean skin) { this.skin = skin; }

    public boolean isHair() { return hair; }
    public void setHair(boolean hair) { this.hair = hair; }

    public int getDownloads() { return downloads; }
    public void setDownloads(int downloads) { this.downloads = downloads; }

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
