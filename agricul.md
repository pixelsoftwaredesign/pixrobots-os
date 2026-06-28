# AgriCol — Système d'Irrigation Agricole Intelligent

## Architecture Globale

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTENDS                            │
│  ┌──────────┐  ┌────────────┐  ┌──────────────────┐    │
│  │  Flutter  │  │  JavaFX    │  │  Web (React)     │    │
│  │  (Mobile) │  │  (Desktop) │  │  (futur)         │    │
│  └────┬─────┘  └─────┬──────┘  └────────┬─────────┘    │
├───────┼───────────────┼──────────────────┼──────────────┤
│       └───────────────┼──────────────────┘              │
│                       │  REST API (JSON)                │
│              ┌────────▼────────┐                        │
│              │   BACKEND       │                        │
│              │  Spring Boot    │  Port 8080             │
│              │                 │                        │
│              │  - Controllers  │                        │
│              │  - Services     │                        │
│              │  - Scheduling   │                        │
│              │  - Security JWT │                        │
│              └───┬────┬────┬───┘                        │
├──────────────────┼────┼────┼───────────────────────────┤
│                  │    │    │                            │
│         ┌────────┘    │    └────────┐                  │
│         ▼             ▼             ▼                  │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│   │  MySQL   │ │  MongoDB  │ │ Mosquitto│              │
│   │ Données  │ │ Time-     │ │ Broker   │              │
│   │ struc-   │ │ Series    │ │ MQTT     │              │
│   │ turées   │ │ capteurs  │ │          │              │
│   └──────────┘ └──────────┘ └────┬─────┘              │
├──────────────────────────────────┼─────────────────────┤
│                                  │ MQTT                │
│                         ┌────────▼────────┐            │
│                         │    EDGE         │            │
│                         │  Raspberry Pi   │            │
│                         │                 │            │
│                         │  Python Script  │            │
│                         │  - Lecture      │            │
│                         │  - Commande     │            │
│                         │  - MQTT Client  │            │
│                         └──┬────────┬─────┘            │
│                            │        │                  │
│                     ┌──────▼──┐ ┌───▼────────┐        │
│                     │Capteurs │ │Électrovannes│        │
│                     │sol/temp │ │(via relais) │        │
│                     └─────────┘ └────────────┘        │
└─────────────────────────────────────────────────────────┘
```

## Structure du Projet

```
agricol/
├── backend/                          # Spring Boot API
│   ├── pom.xml
│   └── src/main/java/com/agricol/
│       ├── AgricolApplication.java
│       ├── config/
│       │   ├── SecurityConfig.java
│       │   └── WebConfig.java
│       ├── controller/
│       │   ├── AuthController.java
│       │   ├── ZoneController.java
│       │   ├── MesureController.java
│       │   └── IrrigationController.java
│       ├── dto/
│       │   ├── MesureRequest.java
│       │   ├── CommandeIrrigation.java
│       │   ├── LoginRequest.java
│       │   └── ZoneDto.java
│       ├── model/
│       │   ├── Zone.java              (JPA - MySQL)
│       │   ├── Utilisateur.java       (JPA - MySQL)
│       │   ├── Role.java
│       │   ├── EvenementIrrigation.java (JPA - MySQL)
│       │   └── MesureCapteur.java     (MongoDB)
│       ├── repository/
│       │   ├── ZoneRepository.java
│       │   ├── UtilisateurRepository.java
│       │   ├── MesureCapteurRepository.java
│       │   └── EvenementIrrigationRepository.java
│       └── service/
│           ├── MesureService.java
│           ├── IrrigationService.java
│           ├── MqttService.java
│           ├── AuthService.java
│           └── ZoneService.java
│
├── edge/                             # Raspberry Pi
│   ├── config.py
│   ├── main.py
│   ├── requirements.txt
│   └── sensors/
│       ├── soil_sensor.py
│       └── relay.py
│
├── mobile/                           # Flutter
│   ├── pubspec.yaml
│   └── lib/
│       ├── main.dart
│       ├── models/
│       │   ├── zone.dart
│       │   └── mesure.dart
│       ├── services/
│       │   └── api_service.dart
│       └── screens/
│           └── dashboard_screen.dart
│
├── desktop/                          # JavaFX
│   ├── pom.xml
│   └── src/main/java/com/agricol/desktop/
│       ├── DesktopApp.java
│       └── DashboardController.java
│
└── docker/                           # Infrastructure
    ├── docker-compose.yml
    └── mosquitto.conf
```

## Stack Technique

| Couche        | Technologie                  |
|---------------|------------------------------|
| Edge          | Raspberry Pi + Python        |
| Backend       | Spring Boot 3.2 + Java 17    |
| DB SQL        | MySQL 8 (zones, users, logs) |
| DB NoSQL      | MongoDB 7 (time-series)      |
| Messaging     | MQTT via Mosquitto           |
| Mobile        | Flutter 3                    |
| Desktop       | JavaFX 21                    |
| Sécurité      | JWT                          |
| Ordonnanceur  | @Scheduled (Spring)          |

## Flux de Données

1. **Capteurs** → GPIO → script Python lit humidité/température
2. **Raspberry Pi** → HTTP POST `/api/mesures` → Spring Boot
3. **Spring Boot** → persist dans MongoDB (time-series)
4. **@Scheduled** (60s) → vérifie seuil → si <30%, publie MQTT + enregistre événement
5. **Mosquitto** → `agricol/vanne/{id}` → Raspberry Pi reçoit → active relais GPIO
6. **Flutter/JavaFX** → GET `/api/zones` → affiche dashboard temps réel

## API REST

| Méthode | Endpoint                  | Rôle                     |
|---------|---------------------------|--------------------------|
| POST    | `/api/auth/login`         | Authentification         |
| GET     | `/api/zones`              | Liste des zones          |
| POST    | `/api/zones`              | Créer une zone           |
| PUT     | `/api/zones/{id}`         | Modifier une zone        |
| DELETE  | `/api/zones/{id}`         | Supprimer une zone       |
| POST    | `/api/mesures`            | Envoyer mesure capteur   |
| GET     | `/api/mesures/{zoneId}`   | Historique mesures       |
| POST    | `/api/irrigation/commande`| Commande manuelle vanne  |
| GET     | `/api/irrigation/historique/{zoneId}` | Événements irrigation |

## Démarrage Rapide

```bash
# 1. Infrastructure (MySQL, MongoDB, Mosquitto)
cd docker
docker-compose up -d

# 2. Backend Spring Boot
cd backend
mvn spring-boot:run

# 3. Raspberry Pi
cd edge
pip install -r requirements.txt
python main.py

# 4. Mobile Flutter
cd mobile
flutter run

# 5. Desktop JavaFX
cd desktop
mvn javafx:run
```

## Prochaines Étapes

- [ ] Définir surface exacte et nombre de zones
- [ ] Choisir type d'alimentation (secteur/solaire)
- [ ] Sélectionner capteurs (capacitifs, DHT22)
- [ ] Configurer GPIO sur le Raspberry Pi
- [ ] Déployer backend sur VPS ou serveur local
- [ ] Ajouter alertes push (Firebase)
- [ ] Interface web (React/Angular)
