package com.agricol.service;

import com.agricol.model.EvenementIrrigation;
import com.agricol.model.MesureCapteur;
import com.agricol.model.Zone;
import com.agricol.repository.EvenementIrrigationRepository;
import com.agricol.repository.MesureCapteurRepository;
import com.agricol.repository.ZoneRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;

@Service
@RequiredArgsConstructor
@Slf4j
public class IrrigationService {

    private final ZoneRepository zoneRepo;
    private final MesureCapteurRepository mesureRepo;
    private final EvenementIrrigationRepository evenementRepo;
    private final MqttService mqttService;

    @Value("${app.irrigation.hysteresis:5.0}")
    private double hysteresis;

    @Scheduled(fixedDelayString = "${app.irrigation.check-interval-ms}")
    public void verifierEtIrriguer() {
        List<Zone> zones = zoneRepo.findAll();

        for (Zone zone : zones) {
            if (Boolean.FALSE.equals(zone.getActive())) continue;

            List<MesureCapteur> dernieres = mesureRepo
                    .findTop20ByZoneIdOrderByTimestampDesc(zone.getId());

            if (dernieres.isEmpty()) continue;

            MesureCapteur derniere = dernieres.get(0);
            double seuil = zone.getSeuilHumidite() != null
                    ? zone.getSeuilHumidite() : 30.0;

            boolean estOuverte = evenementRepo
                    .findFirstByZoneIdOrderByTimestampDesc(zone.getId())
                    .map(e -> "OUVRIR".equals(e.getAction()))
                    .orElse(false);

            boolean doitOuvrir = !estOuverte && derniere.getHumidite() < seuil;
            boolean doitFermer = estOuverte && derniere.getHumidite() >= seuil + hysteresis;

            if (doitOuvrir || doitFermer) {
                EvenementIrrigation evenement = EvenementIrrigation.builder()
                        .zoneId(zone.getId())
                        .declencheur("auto")
                        .humiditeMesuree(derniere.getHumidite())
                        .seuil(seuil)
                        .action(doitOuvrir ? "OUVRIR" : "FERMER")
                        .declenchee(true)
                        .timestamp(Instant.now())
                        .build();

                evenementRepo.save(evenement);
                mqttService.publier(zone.getId(), doitOuvrir);
                log.info("{} vanne zone {} (humidité: {}/{})",
                        doitOuvrir ? "Ouverture" : "Fermeture",
                        zone.getNom(),
                        String.format("%.1f", derniere.getHumidite()),
                        String.format("%.0f", seuil));
            } else {
                evenementRepo.save(EvenementIrrigation.builder()
                        .zoneId(zone.getId())
                        .declencheur("auto")
                        .humiditeMesuree(derniere.getHumidite())
                        .seuil(seuil)
                        .declenchee(false)
                        .timestamp(Instant.now())
                        .build());
            }
        }
    }

    public void commandeManuelle(Long zoneId, boolean ouvrir) {
        Zone zone = zoneRepo.findById(zoneId)
                .orElseThrow(() -> new RuntimeException("Zone introuvable"));

        EvenementIrrigation evenement = EvenementIrrigation.builder()
                .zoneId(zoneId)
                .declencheur("manuel")
                .action(ouvrir ? "OUVRIR" : "FERMER")
                .declenchee(true)
                .timestamp(Instant.now())
                .build();

        evenementRepo.save(evenement);
        mqttService.publier(zoneId, ouvrir);
    }

    public List<EvenementIrrigation> getHistorique(Long zoneId) {
        return evenementRepo.findTop50ByZoneIdOrderByTimestampDesc(zoneId);
    }
}
