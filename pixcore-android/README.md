# pixcore-android

SDK Android partagé pour l'écosystème Pixel OS.

## Modules

| Module | Description |
|--------|-------------|
| `PixCore.kt` | Point d'entrée unique — initialisation, mode nœud |
| `RetrofitClient.kt` | Client API REST (OkHttp + token PixKey) |
| `MqttClient.kt` | Client MQTT (Paho) — capteurs, robots, alertes |
| `HeartbeatManager.kt` | Heartbeat UDP (port 9100, intervalle 60s) |
| `PixKeyManager.kt` | Gestion des clés Ed25519 (Keystore Android) |
| `WalletManager.kt` | Portefeuille BITROOT (Web3j — Gnosis Chain) |
| `DhtManager.kt` | DHT Kademlia simplifiée — découverte de pairs |

## Utilisation

```kotlin
// settings.gradle.kts
includeBuild("../pixcore-android")

// build.gradle.kts
implementation("com.pixelos:pixcore-android:1.0.0")

// Init
PixCore.init(context, "https://serveur:8080", "token-pixkey")
PixCore.nodeMode = true // active Heartbeat + DHT
```

## Licence

MIT
