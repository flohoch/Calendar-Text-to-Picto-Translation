package com.pictogramtranslator.service;

import com.pictogramtranslator.model.*;
import com.pictogramtranslator.model.TranslationResponse.FieldTranslation;
import com.pictogramtranslator.repository.PictogramRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

@Service
public class TranslationService {

    private static final Logger log = LoggerFactory.getLogger(TranslationService.class);

    private final PictogramRepository pictogramRepository;

    public TranslationService(PictogramRepository pictogramRepository) {
        this.pictogramRepository = pictogramRepository;
    }

    /**
     * Translate a calendar event into pictograms by processing each field independently.
     */
    public TranslationResponse translate(TranslationRequest request) {
        return new TranslationResponse(
                translateField(request.getSummary()),
                translateField(request.getLocation()),
                translateField(request.getParticipants())
        );
    }

    /**
     * Translate a single text field into pictograms using exact keyword matching.
     * <p>
     * Algorithm:
     * 1. Lowercase the input and split into tokens on whitespace.
     * 2. For each token, search the MongoDB searchTerms index for an exact match.
     * 3. If found, pick the first result (highest relevance by insertion order).
     * 4. Tokens with no match are collected in unmatchedTokens.
     */
    public FieldTranslation translateField(String text) {
        if (text == null || text.isBlank()) {
            return new FieldTranslation("", List.of(), List.of());
        }

        String normalized = text.strip().toLowerCase();
        String[] tokens = normalized.split("\\s+");

        List<PictogramMatch> matches = new ArrayList<>();
        List<String> unmatched = new ArrayList<>();

        for (String token : tokens) {
            if (token.isEmpty()) continue;

            Optional<PictogramMatch> match = findPictogramForToken(token);
            if (match.isPresent()) {
                matches.add(match.get());
            } else {
                unmatched.add(token);
                log.debug("No pictogram found for token: '{}'", token);
            }
        }

        return new FieldTranslation(text, matches, unmatched);
    }

    /**
     * Look up a single lowercased token against the searchTerms index.
     * Returns the first matching pictogram, if any.
     */
    private Optional<PictogramMatch> findPictogramForToken(String token) {
        List<Pictogram> results = pictogramRepository.findBySearchTermsContaining(token);
        if (results.isEmpty()) {
            return Optional.empty();
        }
        // Pick the first result; could be refined with scoring later
        Pictogram best = results.get(0);
        return Optional.of(new PictogramMatch(token, best));
    }

    /**
     * Retrieve a single pictogram by its ARASAAC _id.
     */
    public Optional<Pictogram> findById(int id) {
        return pictogramRepository.findById(id);
    }

    /**
     * Return the total number of pictograms in the database.
     */
    public long count() {
        return pictogramRepository.count();
    }
}
