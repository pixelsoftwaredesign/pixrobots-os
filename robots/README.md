# Robots — Firmware et protocole Pixel OS

Firmware pour robots agricoles Pixel OS.

## Robots

| Robot | Rôle |
|-------|------|
| Inspecteur | Surveillance des cultures, capteurs embarqués |
| Moissonneur | Récolte autonome |
| Semoir | Plantation et ensemencement |

## Protocole PixRobots

- Communication via MQTT (JSON)
- Topics : `robots/{id}/status`, `robots/{id}/cmd`, `robots/{id}/telemetry`
- Payload : état, batterie, position, capteurs

## Hardware

- ESP32 / Arduino
- Capteurs : température, humidité, caméra, GPS
- Actionneurs : moteurs, servo, pompes

## Licence

MIT
