# PixelNode

Transformez un vieux smartphone en nœud Pixel OS léger — heartbeat, DHT, relai MQTT, client Ethereum.

## Fonctionnalités

- **Foreground Service** — reste actif en arrière-plan
- **Heartbeat UDP** — broadcast toutes les 60s sur le port 9100
- **DHT Kademlia** — 8 pairs par bucket, timeout 5min, réplication 3
- **Relai MQTT** — `sensors/#`, `robots/+/status`, `alerts/#`
- **Light Client Ethereum** — vérification en-têtes Gnosis Chain (Web3j)
- **PixKeyManager** — Keystore Android, EC secp256k1
- **BootReceiver** — démarrage automatique au boot

## Build

```bash
./gradlew assembleDebug
```

## Licence

MIT
