package com.agricol.model;

import jakarta.persistence.*;
import lombok.*;

@Entity
@Table(name = "espaces")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Espace {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String nom;

    private String localisation;

    @Column(name = "superficie_totale")
    private Double superficieTotale;

    private String description;

    @Column(name = "active")
    private Boolean active;
}
