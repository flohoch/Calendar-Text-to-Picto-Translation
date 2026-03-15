package com.pictogramtranslator.repository;

import com.pictogramtranslator.model.Pictogram;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface PictogramRepository extends MongoRepository<Pictogram, Integer> {

    /**
     * Find all pictograms whose pre-computed searchTerms array contains the given term.
     * The data-loader stores every keyword, plural, tag, and category lowercased.
     */
    List<Pictogram> findBySearchTermsContaining(String term);
}
