package com.agricol.controller;

import com.agricol.model.Espace;
import com.agricol.service.EspaceService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/espaces")
@RequiredArgsConstructor
public class EspaceController {

    private final EspaceService espaceService;

    @GetMapping
    public ResponseEntity<List<Espace>> getAll() {
        return ResponseEntity.ok(espaceService.getAll());
    }

    @GetMapping("/{id}")
    public ResponseEntity<Espace> getById(@PathVariable Long id) {
        return ResponseEntity.ok(espaceService.getById(id));
    }

    @PostMapping
    public ResponseEntity<Espace> creer(@RequestBody Espace espace) {
        return ResponseEntity.ok(espaceService.creer(espace));
    }

    @PutMapping("/{id}")
    public ResponseEntity<Espace> update(@PathVariable Long id, @RequestBody Espace espace) {
        return ResponseEntity.ok(espaceService.mettreAJour(id, espace));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> supprimer(@PathVariable Long id) {
        espaceService.supprimer(id);
        return ResponseEntity.noContent().build();
    }
}
