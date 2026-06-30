# Pixel OS — Serveur

API REST, MQTT, et orchestration pour l'écosystème Pixel OS.

## Stack

| Technologie | Usage |
|-------------|-------|
| Go / Node.js | API REST |
| MQTT (Mosquitto) | Communication temps réel capteurs/robots |
| InfluxDB | Métriques et séries temporelles |
| SQLite | Configuration, utilisateurs |
| Docker | Déploiement |

## Services

- **API REST** — authentification PixKey, CRUD ferme/capteurs/robots/missions
- **MQTT Broker** — messages temps réel des appareils
- **Orchestrateur** — planification des missions agricoles
- **Web Dashboard** — interface d'administration

## Démarrage

```bash
docker-compose up -d
```

## Licence

MIT
