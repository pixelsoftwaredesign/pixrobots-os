package com.agricol.controller;

import com.agricol.dto.MesureRequest;
import com.agricol.model.MesureCapteur;
import com.agricol.service.MesureService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.List;

@RestController
@RequestMapping("/api/mesures")
@RequiredArgsConstructor
public class MesureController {

    private final MesureService mesureService;

    @PostMapping
    public ResponseEntity<MesureCapteur> enregistrer(@Valid @RequestBody MesureRequest req) {
        return ResponseEntity.ok(mesureService.enregistrerMesure(req));
    }

    @GetMapping("/{zoneId}")
    public ResponseEntity<List<MesureCapteur>> getMesures(
            @PathVariable Long zoneId,
            @RequestParam(required = false) Instant debut,
            @RequestParam(required = false) Instant fin) {

        if (debut != null && fin != null) {
            return ResponseEntity.ok(mesureService.getMesuresParPeriode(zoneId, debut, fin));
        }
        return ResponseEntity.ok(mesureService.getDernieresMesures(zoneId));
    }
}
