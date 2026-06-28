package com.agricol.service;

import com.agricol.model.Espace;
import com.agricol.repository.EspaceRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class EspaceService {

    private final EspaceRepository espaceRepo;

    public List<Espace> getAll() {
        return espaceRepo.findAll();
    }

    public Espace getById(Long id) {
        return espaceRepo.findById(id)
                .orElseThrow(() -> new RuntimeException("Espace introuvable"));
    }

    public Espace creer(Espace espace) {
        return espaceRepo.save(espace);
    }

    public Espace mettreAJour(Long id, Espace espace) {
        espace.setId(id);
        return espaceRepo.save(espace);
    }

    public void supprimer(Long id) {
        espaceRepo.deleteById(id);
    }
}
