package com.agricol.repository;

import com.agricol.model.MesureCapteur;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.time.Instant;
import java.util.List;

public interface MesureCapteurRepository extends MongoRepository<MesureCapteur, String> {
    List<MesureCapteur> findByZoneIdAndTimestampBetweenOrderByTimestampAsc(
            Long zoneId, Instant debut, Instant fin);
    List<MesureCapteur> findTop20ByZoneIdOrderByTimestampDesc(Long zoneId);
}
