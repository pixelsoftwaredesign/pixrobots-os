package com.agricol.model;

import jakarta.persistence.*;
import lombok.*;

@Entity
@Table(name = "zones")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Zone {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String nom;

    @Column(nullable = false)
    private Double superficie;

    private String culture;

    @Column(name = "seuil_humidite")
    private Double seuilHumidite;

    @Column(name = "vanne_gpio")
    private Integer vanneGpio;

    @Column(name = "capteur_gpio")
    private Integer capteurGpio;

    @Column(name = "espace_id")
    private Long espaceId;

    @Column(name = "active")
    private Boolean active;
}
