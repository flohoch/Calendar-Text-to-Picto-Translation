package com.pictogramtranslator.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.tartarus.snowball.ext.GermanStemmer;

/**
 * Wraps the Lucene Snowball German stemmer for reducing German words
 * to their stem form. This is not full lemmatization but handles
 * common inflections (plurals, verb conjugations, cases).
 *
 * Examples:
 *   "Hunde"   → "hund"
 *   "gegessen" → "gegess"  (imperfect but useful for matching)
 *   "Schulen" → "schul"
 */
@Service
public class GermanStemmerService {

    private static final Logger log = LoggerFactory.getLogger(GermanStemmerService.class);

    /**
     * Stem a single German word. Input should already be lowercased.
     * Returns the stemmed form, or the original if stemming produces
     * an empty result.
     */
    public String stem(String word) {
        if (word == null || word.isBlank()) {
            return word;
        }

        // GermanStemmer is not thread-safe, so create a new instance each call.
        // For high-throughput scenarios, use ThreadLocal instead.
        GermanStemmer stemmer = new GermanStemmer();
        stemmer.setCurrent(word.toLowerCase());
        stemmer.stem();
        String result = stemmer.getCurrent();

        if (result == null || result.isBlank()) {
            return word;
        }

        log.trace("Stemmed '{}' → '{}'", word, result);
        return result;
    }
}
