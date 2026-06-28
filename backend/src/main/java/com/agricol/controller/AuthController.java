package com.agricol.controller;

import com.agricol.dto.LoginRequest;
import com.agricol.dto.RegisterRequest;
import com.agricol.service.AuthService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @PostMapping("/login")
    public ResponseEntity<?> login(@Valid @RequestBody LoginRequest req) {
        String token = authService.login(req);
        return ResponseEntity.ok(Map.of("token", token));
    }

    @PostMapping("/inscription")
    public ResponseEntity<?> inscription(@Valid @RequestBody RegisterRequest req) {
        authService.inscription(req);
        return ResponseEntity.ok(Map.of("message", "Utilisateur créé avec succès"));
    }
}
