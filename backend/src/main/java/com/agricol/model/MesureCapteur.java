package com.agricol.model;

import lombok.*;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;

@Document(collection = "mesures_capteurs")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class MesureCapteur {

    @Id
    private String id;

    private Long zoneId;
    private String zoneNom;
    private Double humidite;
    private Double temperature;
    private Double conductivite;

    private Double humiditeSol;
    private Double phSol;
    private Double npkAzote;
    private Double npkPhosphore;
    private Double npkPotassium;
    private Double temperatureSol;
    private Double temperatureAir;
    private Double humiditeAir;
    private Double pression;
    private Boolean pluie;
    private Double ventKmh;
    private Double luminositeLux;
    private Double debitEauLMin;
    private Double pressionEauBar;

    private Instant timestamp;
}
