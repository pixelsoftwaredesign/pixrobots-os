package com.agricol.model;

import jakarta.persistence.*;
import lombok.*;

import java.time.Instant;

@Entity
@Table(name = "evenements_irrigation")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class EvenementIrrigation {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Long zoneId;
    private String declencheur;
    private Double humiditeMesuree;
    private Double seuil;
    private Boolean declenchee;
    private String action;
    private Instant timestamp;
}
