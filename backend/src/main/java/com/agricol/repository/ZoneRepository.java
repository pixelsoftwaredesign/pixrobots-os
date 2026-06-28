package com.agricol.repository;

import com.agricol.model.Zone;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ZoneRepository extends JpaRepository<Zone, Long> {
    java.util.List<Zone> findByEspaceId(Long espaceId);
}
