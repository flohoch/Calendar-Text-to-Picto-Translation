package com.pictogramtranslator.controller;

import com.pictogramtranslator.model.Pictogram;
import com.pictogramtranslator.model.TranslationRequest;
import com.pictogramtranslator.model.TranslationResponse;
import com.pictogramtranslator.service.TranslationService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api")
public class TranslationController {

    private final TranslationService translationService;

    public TranslationController(TranslationService translationService) {
        this.translationService = translationService;
    }

    /**
     * POST /api/translate
     * Accepts a calendar event and returns pictogram translations for each field.
     */
    @PostMapping("/translate")
    public ResponseEntity<TranslationResponse> translate(@RequestBody TranslationRequest request) {
        TranslationResponse response = translationService.translate(request);
        return ResponseEntity.ok(response);
    }

    /**
     * GET /api/pictograms/{id}
     * Retrieve a single pictogram by ARASAAC ID.
     */
    @GetMapping("/pictograms/{id}")
    public ResponseEntity<Pictogram> getPictogram(@PathVariable int id) {
        return translationService.findById(id)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    /**
     * GET /api/status
     * Health check returning the number of pictograms loaded.
     */
    @GetMapping("/status")
    public ResponseEntity<Map<String, Object>> status() {
        long count = translationService.count();
        return ResponseEntity.ok(Map.of(
                "status", "ok",
                "pictogramCount", count
        ));
    }
}
