package com.agricol.service;

import com.agricol.dto.LoginRequest;
import com.agricol.dto.RegisterRequest;
import com.agricol.model.Utilisateur;
import com.agricol.repository.UtilisateurRepository;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UtilisateurRepository userRepo;
    private final PasswordEncoder passwordEncoder;

    @Value("${app.jwt.secret}")
    private String jwtSecret;

    @Value("${app.jwt.expiration}")
    private long jwtExpiration;

    public void inscription(RegisterRequest req) {
        if (userRepo.findByEmail(req.getEmail()).isPresent()) {
            throw new RuntimeException("Email déjà utilisé");
        }
        Utilisateur user = Utilisateur.builder()
                .email(req.getEmail())
                .motDePasse(passwordEncoder.encode(req.getMotDePasse()))
                .nom(req.getNom())
                .role(req.getRole())
                .build();
        userRepo.save(user);
    }

    public String login(LoginRequest req) {
        Utilisateur user = userRepo.findByEmail(req.getEmail())
                .orElseThrow(() -> new RuntimeException("Email ou mot de passe incorrect"));

        if (!passwordEncoder.matches(req.getMotDePasse(), user.getMotDePasse())) {
            throw new RuntimeException("Email ou mot de passe incorrect");
        }

        SecretKey key = Keys.hmacShaKeyFor(jwtSecret.getBytes(StandardCharsets.UTF_8));

        return Jwts.builder()
                .subject(user.getId().toString())
                .claim("email", user.getEmail())
                .claim("role", user.getRole().name())
                .issuedAt(new Date())
                .expiration(new Date(System.currentTimeMillis() + jwtExpiration))
                .signWith(key)
                .compact();
    }
}
