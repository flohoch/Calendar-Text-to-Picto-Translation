package com.pictogramtranslator.service;

import com.pictogramtranslator.model.Keyword;
import com.pictogramtranslator.model.Pictogram;
import com.pictogramtranslator.repository.PictogramRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import java.util.*;

/**
 * Builds and holds in-memory indices over the ARASAAC pictogram database
 * to enable fast multi-strategy lookups without repeated MongoDB queries.
 *
 * Indices built at startup:
 * - searchTerm → List of Pictograms     (exact lowercased keyword/tag/category match)
 * - stem       → List of Pictograms     (stemmed keywords for fuzzy matching)
 * - synsetId   → List of Pictograms     (ARASAAC synset → pictograms)
 * - keyword    → List of synset IDs     (reverse: from keyword to its synsets)
 */
@Service
public class PictogramIndexService {

    private static final Logger log = LoggerFactory.getLogger(PictogramIndexService.class);

    private final PictogramRepository pictogramRepository;
    private final GermanStemmerService stemmerService;

    /** Exact lowercased term → pictograms. Includes multi-word keywords. */
    private final Map<String, List<Pictogram>> exactIndex = new HashMap<>();

    /** Stemmed term → pictograms. Built by stemming every keyword. */
    private final Map<String, List<Pictogram>> stemIndex = new HashMap<>();

    /** ARASAAC synset ID (e.g. "02209508-n") → pictograms having that synset. */
    private final Map<String, List<Pictogram>> synsetIndex = new HashMap<>();

    /** Lowercased keyword → synset IDs from the pictogram that keyword belongs to. */
    private final Map<String, Set<String>> keywordToSynsets = new HashMap<>();

    private long totalPictograms = 0;

    public PictogramIndexService(PictogramRepository pictogramRepository,
                                  GermanStemmerService stemmerService) {
        this.pictogramRepository = pictogramRepository;
        this.stemmerService = stemmerService;
    }

    @PostConstruct
    public void buildIndices() {
        log.info("Building in-memory pictogram indices...");
        List<Pictogram> allPictograms = pictogramRepository.findAll();
        totalPictograms = allPictograms.size();

        for (Pictogram p : allPictograms) {
            // --- Exact index: from searchTerms (already lowercased) ---
            if (p.getSearchTerms() != null) {
                for (String term : p.getSearchTerms()) {
                    exactIndex.computeIfAbsent(term, k -> new ArrayList<>()).add(p);
                }
            }

            // --- Keyword-based stem index and keyword→synset mapping ---
            List<String> synsets = p.getSynsets() != null ? p.getSynsets() : List.of();

            if (p.getKeywords() != null) {
                for (Keyword kw : p.getKeywords()) {
                    String keyword = kw.getKeyword();
                    if (keyword == null || keyword.isBlank()) continue;

                    String lower = keyword.strip().toLowerCase();

                    // Map keyword → synsets (for synset-based fallback)
                    if (!synsets.isEmpty()) {
                        keywordToSynsets.computeIfAbsent(lower, k -> new HashSet<>())
                                .addAll(synsets);
                    }

                    // Stem each word in the keyword and index by stems
                    String[] words = lower.split("\\s+");
                    for (String word : words) {
                        String stemmed = stemmerService.stem(word);
                        stemIndex.computeIfAbsent(stemmed, k -> new ArrayList<>()).add(p);
                    }

                    // Also stem plurals
                    String plural = kw.getPlural();
                    if (plural != null && !plural.isBlank()) {
                        String stemmedPlural = stemmerService.stem(plural.strip().toLowerCase());
                        stemIndex.computeIfAbsent(stemmedPlural, k -> new ArrayList<>()).add(p);
                    }
                }
            }

            // --- Synset index ---
            for (String synsetId : synsets) {
                synsetIndex.computeIfAbsent(synsetId, k -> new ArrayList<>()).add(p);
            }
        }

        log.info("Index build complete. {} pictograms, {} exact terms, {} stems, {} synsets.",
                totalPictograms, exactIndex.size(), stemIndex.size(), synsetIndex.size());
    }

    /**
     * Exact match against lowercased searchTerms.
     * Works for both single words and multi-word phrases (e.g. "an einem seil gehen").
     */
    public List<Pictogram> findByExactTerm(String term) {
        return exactIndex.getOrDefault(term, List.of());
    }

    /**
     * Match by stemmed form of the input token.
     */
    public List<Pictogram> findByStem(String stem) {
        return stemIndex.getOrDefault(stem, List.of());
    }

    /**
     * Find pictograms that have the given synset ID.
     */
    public List<Pictogram> findBySynset(String synsetId) {
        return synsetIndex.getOrDefault(synsetId, List.of());
    }

    /**
     * Get synset IDs associated with a lowercased keyword.
     * Used to bootstrap synset matching: keyword → synsets → hypernyms → pictograms.
     */
    public Set<String> getSynsetsForKeyword(String keyword) {
        return keywordToSynsets.getOrDefault(keyword, Set.of());
    }

    /**
     * Find pictograms matching any of the given synset IDs.
     */
    public List<Pictogram> findByAnySynset(Collection<String> synsetIds) {
        List<Pictogram> results = new ArrayList<>();
        Set<Integer> seenIds = new HashSet<>();
        for (String sid : synsetIds) {
            for (Pictogram p : findBySynset(sid)) {
                if (seenIds.add(p.getId())) {
                    results.add(p);
                }
            }
        }
        return results;
    }

    public long getTotalPictograms() {
        return totalPictograms;
    }
}
