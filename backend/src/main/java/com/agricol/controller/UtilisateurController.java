package com.agricol.controller;

import com.agricol.dto.RegisterRequest;
import com.agricol.model.Utilisateur;
import com.agricol.repository.UtilisateurRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/utilisateurs")
@RequiredArgsConstructor
public class UtilisateurController {

    private final UtilisateurRepository userRepo;

    @GetMapping
    public ResponseEntity<List<Utilisateur>> getAll() {
        return ResponseEntity.ok(userRepo.findAll());
    }

    @GetMapping("/{id}")
    public ResponseEntity<Utilisateur> getById(@PathVariable Long id) {
        return ResponseEntity.ok(userRepo.findById(id)
                .orElseThrow(() -> new RuntimeException("Utilisateur introuvable")));
    }

    @PutMapping("/{id}")
    public ResponseEntity<Utilisateur> update(@PathVariable Long id, @RequestBody RegisterRequest req) {
        Utilisateur user = userRepo.findById(id)
                .orElseThrow(() -> new RuntimeException("Utilisateur introuvable"));
        user.setEmail(req.getEmail());
        user.setNom(req.getNom());
        user.setRole(req.getRole());
        if (req.getMotDePasse() != null && !req.getMotDePasse().isBlank()) {
            user.setMotDePasse(req.getMotDePasse());
        }
        return ResponseEntity.ok(userRepo.save(user));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> supprimer(@PathVariable Long id) {
        userRepo.deleteById(id);
        return ResponseEntity.noContent().build();
    }
}
