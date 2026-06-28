package com.agricol.controller;

import com.agricol.dto.ZoneDto;
import com.agricol.model.Zone;
import com.agricol.service.ZoneService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class ZoneController {

    private final ZoneService zoneService;

    @GetMapping("/zones")
    public ResponseEntity<List<ZoneDto>> getAll() {
        return ResponseEntity.ok(zoneService.getAllZones());
    }

    @GetMapping("/zones/{id}")
    public ResponseEntity<ZoneDto> getById(@PathVariable Long id) {
        return ResponseEntity.ok(zoneService.getZone(id));
    }

    @GetMapping("/espaces/{espaceId}/zones")
    public ResponseEntity<List<ZoneDto>> getByEspace(@PathVariable Long espaceId) {
        return ResponseEntity.ok(zoneService.getZonesByEspace(espaceId));
    }

    @PostMapping("/espaces/{espaceId}/zones")
    public ResponseEntity<Zone> creer(@PathVariable Long espaceId, @RequestBody Zone zone) {
        return ResponseEntity.ok(zoneService.creer(espaceId, zone));
    }

    @PutMapping("/zones/{id}")
    public ResponseEntity<Zone> update(@PathVariable Long id, @RequestBody Zone zone) {
        return ResponseEntity.ok(zoneService.mettreAJour(id, zone));
    }

    @DeleteMapping("/zones/{id}")
    public ResponseEntity<Void> supprimer(@PathVariable Long id) {
        zoneService.supprimer(id);
        return ResponseEntity.noContent().build();
    }
}
