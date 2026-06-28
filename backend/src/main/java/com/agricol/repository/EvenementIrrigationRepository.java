package com.agricol.repository;

import com.agricol.model.EvenementIrrigation;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface EvenementIrrigationRepository extends JpaRepository<EvenementIrrigation, Long> {
    List<EvenementIrrigation> findTop50ByZoneIdOrderByTimestampDesc(Long zoneId);
    Optional<EvenementIrrigation> findFirstByZoneIdOrderByTimestampDesc(Long zoneId);
}
