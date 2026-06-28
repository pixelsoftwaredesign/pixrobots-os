package com.agricol.dto;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class MesureRequest {
    @NotNull
    private Long zoneId;
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
}
