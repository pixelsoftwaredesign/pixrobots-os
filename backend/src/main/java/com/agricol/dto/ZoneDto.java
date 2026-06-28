package com.agricol.dto;

import lombok.Data;

@Data
public class ZoneDto {
    private Long id;
    private String nom;
    private Double superficie;
    private String culture;
    private Double seuilHumidite;
    private Long espaceId;
    private String espaceNom;
    private Boolean active;
    private Double derniereHumidite;
    private String derniereMesure;
}
