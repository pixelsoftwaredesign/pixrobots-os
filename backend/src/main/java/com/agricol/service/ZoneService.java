package com.agricol.service;

import com.agricol.dto.ZoneDto;
import com.agricol.model.Espace;
import com.agricol.model.MesureCapteur;
import com.agricol.model.Zone;
import com.agricol.repository.EspaceRepository;
import com.agricol.repository.MesureCapteurRepository;
import com.agricol.repository.ZoneRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class ZoneService {

    private final ZoneRepository zoneRepo;
    private final EspaceRepository espaceRepo;
    private final MesureCapteurRepository mesureRepo;

    public List<ZoneDto> getAllZones() {
        return zoneRepo.findAll().stream()
                .map(this::toDto)
                .collect(Collectors.toList());
    }

    public List<ZoneDto> getZonesByEspace(Long espaceId) {
        return zoneRepo.findByEspaceId(espaceId).stream()
                .map(this::toDto)
                .collect(Collectors.toList());
    }

    public ZoneDto getZone(Long id) {
        Zone zone = zoneRepo.findById(id)
                .orElseThrow(() -> new RuntimeException("Zone introuvable"));
        return toDto(zone);
    }

    public Zone creer(Long espaceId, Zone zone) {
        espaceRepo.findById(espaceId)
                .orElseThrow(() -> new RuntimeException("Espace introuvable"));
        zone.setEspaceId(espaceId);
        return zoneRepo.save(zone);
    }

    public Zone mettreAJour(Long id, Zone zone) {
        zone.setId(id);
        return zoneRepo.save(zone);
    }

    public void supprimer(Long id) {
        zoneRepo.deleteById(id);
    }

    private ZoneDto toDto(Zone zone) {
        ZoneDto dto = new ZoneDto();
        dto.setId(zone.getId());
        dto.setNom(zone.getNom());
        dto.setSuperficie(zone.getSuperficie());
        dto.setCulture(zone.getCulture());
        dto.setSeuilHumidite(zone.getSeuilHumidite());
        dto.setEspaceId(zone.getEspaceId());
        dto.setActive(zone.getActive());

        if (zone.getEspaceId() != null) {
            espaceRepo.findById(zone.getEspaceId()).ifPresent(e ->
                    dto.setEspaceNom(e.getNom()));
        }

        List<MesureCapteur> dernieres = mesureRepo
                .findTop20ByZoneIdOrderByTimestampDesc(zone.getId());
        if (!dernieres.isEmpty()) {
            dto.setDerniereHumidite(dernieres.get(0).getHumidite());
            dto.setDerniereMesure(dernieres.get(0).getTimestamp().toString());
        }
        return dto;
    }
}
