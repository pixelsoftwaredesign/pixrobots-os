# PixConnect

Centre de contrôle réseau pour Pixel OS — WiFi, Bluetooth, données, mesh et firewall.

## Modules

| Module | Description |
|--------|-------------|
| **Wi-Fi** | Scan, connexion, hotspot, profils réseaux |
| **Bluetooth** | Scan BLE/classic, pairage, capteurs agricoles |
| **Données** | Monitoring par app, limites, alertes |
| **Mesh PixNet** | Paires WireGuard, latence, partage de connexion |
| **Firewall PixDefend** | Règles globales, blocage par application |
| **Profils** | Basculer ferme/maison/champ en un tap |

## Permissions

- `ACCESS_WIFI_STATE`, `CHANGE_WIFI_STATE`
- `BLUETOOTH`, `BLUETOOTH_ADMIN`, `BLUETOOTH_SCAN`, `BLUETOOTH_CONNECT`
- `PACKAGE_USAGE_STATS` (monitoring données)
- `ACCESS_FINE_LOCATION` (scan WiFi/BT)

## Build

```bash
./gradlew assembleDebug
```

## Licence

MIT
