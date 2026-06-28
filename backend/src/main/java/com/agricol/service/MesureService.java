package com.agricol.service;

import com.agricol.dto.MesureRequest;
import com.agricol.model.MesureCapteur;
import com.agricol.model.Zone;
import com.agricol.repository.MesureCapteurRepository;
import com.agricol.repository.ZoneRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;

@Service
@RequiredArgsConstructor
public class MesureService {

    private final MesureCapteurRepository mesureRepo;
    private final ZoneRepository zoneRepo;

    public MesureCapteur enregistrerMesure(MesureRequest req) {
        Zone zone = zoneRepo.findById(req.getZoneId())
                .orElseThrow(() -> new RuntimeException("Zone introuvable"));

        MesureCapteur mesure = MesureCapteur.builder()
                .zoneId(zone.getId())
                .zoneNom(zone.getNom())
                .humidite(req.getHumidite())
                .temperature(req.getTemperature())
                .conductivite(req.getConductivite())
                .humiditeSol(req.getHumiditeSol())
                .phSol(req.getPhSol())
                .npkAzote(req.getNpkAzote())
                .npkPhosphore(req.getNpkPhosphore())
                .npkPotassium(req.getNpkPotassium())
                .temperatureSol(req.getTemperatureSol())
                .temperatureAir(req.getTemperatureAir())
                .humiditeAir(req.getHumiditeAir())
                .pression(req.getPression())
                .pluie(req.getPluie())
                .ventKmh(req.getVentKmh())
                .luminositeLux(req.getLuminositeLux())
                .debitEauLMin(req.getDebitEauLMin())
                .pressionEauBar(req.getPressionEauBar())
                .timestamp(Instant.now())
                .build();

        return mesureRepo.save(mesure);
    }

    public List<MesureCapteur> getDernieresMesures(Long zoneId) {
        return mesureRepo.findTop20ByZoneIdOrderByTimestampDesc(zoneId);
    }

    public List<MesureCapteur> getMesuresParPeriode(Long zoneId, Instant debut, Instant fin) {
        return mesureRepo.findByZoneIdAndTimestampBetweenOrderByTimestampAsc(zoneId, debut, fin);
    }
}
