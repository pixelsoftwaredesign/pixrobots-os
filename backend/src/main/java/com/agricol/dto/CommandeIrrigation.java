package com.agricol.dto;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class CommandeIrrigation {
    @NotNull
    private Long zoneId;
    @NotNull
    private Boolean ouvrir;
}
