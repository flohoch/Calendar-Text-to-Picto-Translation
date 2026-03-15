package com.pictogramtranslator.service;

import com.pictogramtranslator.model.*;
import com.pictogramtranslator.model.PictogramMatch.MatchType;
import com.pictogramtranslator.model.TranslationResponse.FieldTranslation;
import com.pictogramtranslator.repository.PictogramRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.*;

/**
 * Hybrid pictogram translation pipeline for calendar event fields.
 *
 * Processing order (per field):
 *
 * 1. MULTI-WORD SLIDING WINDOW — Starting from each token position, try the
 *    longest possible phrase first, shrinking the window until a match is found.
 *    This handles ARASAAC multi-word keywords like "an einem Seil gehen".
 *
 * 2. EXACT KEYWORD MATCH — For single tokens that weren't consumed by
 *    multi-word matching, check the lowercased searchTerms index.
 *
 * 3. STEMMED MATCH — Stem the token using the German Snowball stemmer,
 *    then check the pre-built stem index. Handles inflections like
 *    "Hunde" → "hund" matching the pictogram for "Hund".
 *
 * 4. SYNSET MATCH — Look up synsets associated with the stemmed keyword
 *    (via the ARASAAC keyword→synset mapping), traverse WordNet hypernyms,
 *    and check if any parent synset matches a pictogram.
 *    Example: "Lachs" (salmon) → hypernym "Fisch" (fish) → pictogram found.
 *
 * 5. UNMATCHED — Token is flagged for caregiver review.
 */
@Service
public class TranslationService {

    private static final Logger log = LoggerFactory.getLogger(TranslationService.class);

    private final PictogramRepository pictogramRepository;
    private final PictogramIndexService indexService;
    private final GermanStemmerService stemmerService;
    private final SynsetService synsetService;

    public TranslationService(PictogramRepository pictogramRepository,
                              PictogramIndexService indexService,
                              GermanStemmerService stemmerService,
                              SynsetService synsetService) {
        this.pictogramRepository = pictogramRepository;
        this.indexService = indexService;
        this.stemmerService = stemmerService;
        this.synsetService = synsetService;
    }

    /**
     * Translate a calendar event into pictograms by processing each field.
     */
    public TranslationResponse translate(TranslationRequest request) {
        return new TranslationResponse(
                translateField(request.getSummary()),
                translateField(request.getLocation()),
                translateField(request.getParticipants())
        );
    }

    /**
     * Translate a single text field through the full tiered pipeline.
     */
    public FieldTranslation translateField(String text) {
        if (text == null || text.isBlank()) {
            return new FieldTranslation("", List.of(), List.of());
        }

        String normalized = text.strip().toLowerCase();
        String[] tokens = normalized.split("\\s+");

        List<PictogramMatch> matches = new ArrayList<>();
        List<String> unmatched = new ArrayList<>();

        int i = 0;
        while (i < tokens.length) {
            boolean matched = false;

            // --- Tier 1: Multi-word sliding window (longest match first) ---
            if (tokens.length - i > 1) {
                for (int windowSize = tokens.length - i; windowSize > 1; windowSize--) {
                    String phrase = joinTokens(tokens, i, i + windowSize);
                    List<Pictogram> results = indexService.findByExactTerm(phrase);
                    if (!results.isEmpty()) {
                        matches.add(new PictogramMatch(phrase, results.get(0), MatchType.EXACT));
                        log.debug("EXACT multi-word match: '{}' → pictogram {}", phrase, results.get(0).getId());
                        i += windowSize;
                        matched = true;
                        break;
                    }
                }
            }
            if (matched) continue;

            String token = tokens[i];

            // --- Tier 2: Exact single-token match ---
            List<Pictogram> exactResults = indexService.findByExactTerm(token);
            if (!exactResults.isEmpty()) {
                matches.add(new PictogramMatch(token, exactResults.get(0), MatchType.EXACT));
                log.debug("EXACT match: '{}' → pictogram {}", token, exactResults.get(0).getId());
                i++;
                continue;
            }

            // --- Tier 3: Stemmed match ---
            String stemmed = stemmerService.stem(token);
            List<Pictogram> stemResults = indexService.findByStem(stemmed);
            if (!stemResults.isEmpty()) {
                matches.add(new PictogramMatch(token, stemResults.get(0), MatchType.STEMMED));
                log.debug("STEMMED match: '{}' (stem: '{}') → pictogram {}", token, stemmed, stemResults.get(0).getId());
                i++;
                continue;
            }

            // --- Tier 4: Synset match via hypernym traversal ---
            PictogramMatch synsetMatch = trySynsetMatch(token, stemmed);
            if (synsetMatch != null) {
                matches.add(synsetMatch);
                log.debug("SYNSET match: '{}' → pictogram {}", token, synsetMatch.getPictogramId());
                i++;
                continue;
            }

            // --- Tier 5: Unmatched ---
            log.debug("UNMATCHED: '{}'", token);
            unmatched.add(token);
            i++;
        }

        return new FieldTranslation(text, matches, unmatched);
    }

    /**
     * Attempt synset-based matching:
     * 1. Find synsets associated with the token or its stem (via keyword→synset mapping).
     * 2. Check if any pictogram directly shares those synsets.
     * 3. Traverse WordNet hypernyms and check for matches at each level.
     */
    private PictogramMatch trySynsetMatch(String token, String stemmed) {
        // Collect synsets from the token itself and its stem
        Set<String> candidateSynsets = new HashSet<>();
        candidateSynsets.addAll(indexService.getSynsetsForKeyword(token));
        if (!stemmed.equals(token)) {
            candidateSynsets.addAll(indexService.getSynsetsForKeyword(stemmed));
        }

        if (candidateSynsets.isEmpty()) {
            return null;
        }

        // Direct synset match: another pictogram shares the same synset
        List<Pictogram> directMatches = indexService.findByAnySynset(candidateSynsets);
        if (!directMatches.isEmpty()) {
            return new PictogramMatch(token, directMatches.get(0), MatchType.SYNSET);
        }

        // Hypernym traversal: walk up the WordNet tree
        if (synsetService.isAvailable()) {
            Set<String> hypernyms = synsetService.getHypernymsForAll(candidateSynsets);
            List<Pictogram> hypernymMatches = indexService.findByAnySynset(hypernyms);
            if (!hypernymMatches.isEmpty()) {
                return new PictogramMatch(token, hypernymMatches.get(0), MatchType.SYNSET);
            }
        }

        return null;
    }

    /**
     * Join tokens[from..to) with spaces.
     */
    private String joinTokens(String[] tokens, int from, int to) {
        StringJoiner joiner = new StringJoiner(" ");
        for (int i = from; i < to; i++) {
            joiner.add(tokens[i]);
        }
        return joiner.toString();
    }

    public Optional<Pictogram> findById(int id) {
        return pictogramRepository.findById(id);
    }

    public long count() {
        return indexService.getTotalPictograms();
    }
}
