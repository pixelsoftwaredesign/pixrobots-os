-- =============================================================
-- PixelOS - Base de Donnees Agronomique Complete
-- Categories, Familles, Plantes, Varietes, Calendrier,
-- Irrigation, Maladies, Analyses Sol, Microbiologie
-- =============================================================

CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    icone VARCHAR(50)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS familles_botaniques (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS plantes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nom_commun VARCHAR(150) NOT NULL,
    nom_scientifique VARCHAR(200) NOT NULL,
    id_categorie INT NOT NULL,
    id_famille INT,
    cycle_vie ENUM('annuel','bisannuel','perenne','vivace') DEFAULT 'annuel',
    description TEXT,
    image_url VARCHAR(500),
    FOREIGN KEY (id_categorie) REFERENCES categories(id),
    FOREIGN KEY (id_famille) REFERENCES familles_botaniques(id),
    UNIQUE KEY uk_nom_sci (nom_scientifique)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS varietes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_plante INT NOT NULL,
    nom VARCHAR(150) NOT NULL,
    besoin_eau ENUM('faible','moyen','elevetres_eleve') DEFAULT 'moyen',
    type_sol_ideal VARCHAR(200),
    rendement_estime DECIMAL(10,2),
    resistance_maladies TEXT,
    origine VARCHAR(200),
    notes TEXT,
    FOREIGN KEY (id_plante) REFERENCES plantes(id),
    UNIQUE KEY uk_variete (id_plante, nom)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS calendrier_culture (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_variete INT NOT NULL,
    zone_climatique VARCHAR(100) DEFAULT 'tempere',
    mois_semis_debut INT,
    mois_semis_fin INT,
    mois_plantation_debut INT,
    mois_plantation_fin INT,
    mois_recolte_debut INT,
    mois_recolte_fin INT,
    duree_cycle_jours INT,
    periode_floraison VARCHAR(100),
    FOREIGN KEY (id_variete) REFERENCES varietes(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS irrigation (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_variete INT NOT NULL,
    methode VARCHAR(100) COMMENT 'goutte-a-goutte, aspersion, gravitaire, pluvial',
    frequence_mm_semaine DECIMAL(6,2),
    frequence_jours INT COMMENT 'Tous les X jours',
    duree_minutes INT,
    stade_critique VARCHAR(200) COMMENT 'Periodes critiques besoin eau',
    notes TEXT,
    FOREIGN KEY (id_variete) REFERENCES varietes(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS maladies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(200) NOT NULL UNIQUE,
    type_agent ENUM('champignon','bacterie','virus','insecte','carence','autre') DEFAULT 'champignon',
    type_traitement VARCHAR(500),
    description TEXT,
    prevention VARCHAR(500)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS plantes_maladies (
    id_plante INT NOT NULL,
    id_maladie INT NOT NULL,
    sensibilite ENUM('faible','moyenne','forte') DEFAULT 'moyenne',
    PRIMARY KEY (id_plante, id_maladie),
    FOREIGN KEY (id_plante) REFERENCES plantes(id),
    FOREIGN KEY (id_maladie) REFERENCES maladies(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS analyses_sol (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_zone BIGINT,
    date_analyse DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ph DECIMAL(4,2),
    azote_total DECIMAL(6,2) COMMENT 'g/kg',
    phosphore_assim DECIMAL(6,2) COMMENT 'ppm',
    potassium_ech DECIMAL(6,2) COMMENT 'ppm',
    matiere_organique DECIMAL(5,2) COMMENT '%',
    calcaire_total DECIMAL(5,2) COMMENT '%',
    conductivite DECIMAL(6,2) COMMENT 'mS/cm',
    cec DECIMAL(6,2) COMMENT 'meq/100g',
    texture VARCHAR(100) COMMENT 'argileuse, limoneuse, sableuse',
    notes TEXT,
    FOREIGN KEY (id_zone) REFERENCES zones(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS microbiologie_sol (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_analyse INT NOT NULL,
    type_organisme VARCHAR(200),
    categorie ENUM('bacterie','champignon','actinomycete','protozoaire','nematode') DEFAULT 'bacterie',
    role ENUM('benefique','pathogene','neutre') DEFAULT 'benefique',
    densite_population VARCHAR(100) COMMENT 'UFC/g ou estimation',
    seuil_critique VARCHAR(100),
    recommandation TEXT,
    FOREIGN KEY (id_analyse) REFERENCES analyses_sol(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS guides_culture (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_plante INT NOT NULL,
    type_guide ENUM('semis','plantation','entretien','taille','recolte','stockage','rotation') NOT NULL,
    titre VARCHAR(200),
    contenu TEXT,
    saison_recommandee VARCHAR(100),
    FOREIGN KEY (id_plante) REFERENCES plantes(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
