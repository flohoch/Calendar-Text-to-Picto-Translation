package com.pictogramtranslator.model;

public class TranslationRequest {

    private String summary;
    private String location;
    private String participants;

    public TranslationRequest() {}

    public TranslationRequest(String summary, String location, String participants) {
        this.summary = summary;
        this.location = location;
        this.participants = participants;
    }

    public String getSummary() { return summary; }
    public void setSummary(String summary) { this.summary = summary; }

    public String getLocation() { return location; }
    public void setLocation(String location) { this.location = location; }

    public String getParticipants() { return participants; }
    public void setParticipants(String participants) { this.participants = participants; }
}
