package com.agricol.controller;

import com.agricol.dto.CommandeIrrigation;
import com.agricol.model.EvenementIrrigation;
import com.agricol.service.IrrigationService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/irrigation")
@RequiredArgsConstructor
public class IrrigationController {

    private final IrrigationService irrigationService;

    @PostMapping("/commande")
    public ResponseEntity<Void> commander(@Valid @RequestBody CommandeIrrigation cmd) {
        irrigationService.commandeManuelle(cmd.getZoneId(), cmd.getOuvrir());
        return ResponseEntity.ok().build();
    }

    @GetMapping("/historique/{zoneId}")
    public ResponseEntity<List<EvenementIrrigation>> historique(@PathVariable Long zoneId) {
        return ResponseEntity.ok(irrigationService.getHistorique(zoneId));
    }
}
