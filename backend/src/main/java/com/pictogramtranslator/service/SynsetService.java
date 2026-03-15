package com.pictogramtranslator.service;

import net.sf.extjwnl.JWNLException;
import net.sf.extjwnl.data.POS;
import net.sf.extjwnl.data.PointerUtils;
import net.sf.extjwnl.data.Synset;
import net.sf.extjwnl.data.list.PointerTargetNode;
import net.sf.extjwnl.data.list.PointerTargetNodeList;
import net.sf.extjwnl.dictionary.Dictionary;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import java.util.*;

/**
 * Provides WordNet-based synset operations:
 * - Parse ARASAAC synset IDs (e.g. "02209508-n") into WordNet offset + POS.
 * - Traverse hypernym chains to find semantically related synsets.
 *
 * This allows matching an input word to a pictogram when no exact keyword
 * match exists, but the input word's synset is a hyponym (more specific)
 * of a pictogram's synset.
 *
 * Example: "Dackel" (dachshund) → synset is a hyponym of "Hund" (dog)
 *          → matches the pictogram for "Hund".
 */
@Service
public class SynsetService {

    private static final Logger log = LoggerFactory.getLogger(SynsetService.class);

    /** Maximum depth to traverse the hypernym tree. */
    private static final int MAX_HYPERNYM_DEPTH = 4;

    private Dictionary dictionary;
    private boolean available = false;

    @PostConstruct
    public void init() {
        try {
            dictionary = Dictionary.getDefaultResourceInstance();
            available = true;
            log.info("WordNet dictionary loaded successfully.");
        } catch (JWNLException e) {
            log.warn("Could not load WordNet dictionary. Synset matching will be disabled. Reason: {}", e.getMessage());
        }
    }

    public boolean isAvailable() {
        return available;
    }

    /**
     * Parse an ARASAAC-format synset ID like "02209508-n" into a POS and offset.
     * Format: {offset}-{pos_char} where pos_char is n/v/a/r.
     *
     * @return the parsed synset, or empty if the format is invalid
     */
    public Optional<Synset> resolve(String arasaacSynsetId) {
        if (!available || arasaacSynsetId == null || arasaacSynsetId.length() < 3) {
            return Optional.empty();
        }

        try {
            int dashIdx = arasaacSynsetId.lastIndexOf('-');
            if (dashIdx < 1) return Optional.empty();

            long offset = Long.parseLong(arasaacSynsetId.substring(0, dashIdx));
            char posChar = arasaacSynsetId.charAt(dashIdx + 1);
            POS pos = charToPOS(posChar);
            if (pos == null) return Optional.empty();

            Synset synset = dictionary.getSynsetAt(pos, offset);
            return Optional.ofNullable(synset);
        } catch (NumberFormatException | JWNLException e) {
            log.trace("Could not resolve synset '{}': {}", arasaacSynsetId, e.getMessage());
            return Optional.empty();
        }
    }

    /**
     * Collect all hypernym synset IDs (ARASAAC format) reachable from the
     * given synset, up to MAX_HYPERNYM_DEPTH levels.
     *
     * @param arasaacSynsetId starting synset in "offset-pos" format
     * @return set of ARASAAC-format synset IDs for all hypernyms found
     */
    public Set<String> getHypernyms(String arasaacSynsetId) {
        Set<String> result = new HashSet<>();
        if (!available) return result;

        Optional<Synset> optSynset = resolve(arasaacSynsetId);
        if (optSynset.isEmpty()) return result;

        collectHypernyms(optSynset.get(), result, 0);
        return result;
    }

    /**
     * Collect hypernyms for a set of synset IDs.
     */
    public Set<String> getHypernymsForAll(Collection<String> synsetIds) {
        Set<String> allHypernyms = new HashSet<>();
        for (String sid : synsetIds) {
            allHypernyms.addAll(getHypernyms(sid));
        }
        return allHypernyms;
    }

    private void collectHypernyms(Synset synset, Set<String> collector, int depth) {
        if (depth >= MAX_HYPERNYM_DEPTH) return;

        try {
            PointerTargetNodeList hypernyms = PointerUtils.getDirectHypernyms(synset);
            for (PointerTargetNode node : hypernyms) {
                Synset hyperSynset = node.getSynset();
                String hyperId = toArasaacFormat(hyperSynset);
                if (hyperId != null && collector.add(hyperId)) {
                    // Only recurse if this is a new synset (avoid cycles)
                    collectHypernyms(hyperSynset, collector, depth + 1);
                }
            }
        } catch (JWNLException e) {
            log.trace("Error traversing hypernyms at depth {}: {}", depth, e.getMessage());
        }
    }

    /**
     * Convert a WordNet Synset back to ARASAAC format "offset-pos".
     */
    public String toArasaacFormat(Synset synset) {
        if (synset == null) return null;
        char posChar = posToChar(synset.getPOS());
        if (posChar == '?') return null;
        return String.format("%08d-%c", synset.getOffset(), posChar);
    }

    private POS charToPOS(char c) {
        return switch (c) {
            case 'n' -> POS.NOUN;
            case 'v' -> POS.VERB;
            case 'a' -> POS.ADJECTIVE;
            case 'r' -> POS.ADVERB;
            default -> null;
        };
    }

    private char posToChar(POS pos) {
        if (pos == POS.NOUN) return 'n';
        if (pos == POS.VERB) return 'v';
        if (pos == POS.ADJECTIVE) return 'a';
        if (pos == POS.ADVERB) return 'r';
        return '?';
    }
}
