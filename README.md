# 🌱 Pixel OS

**Système d'exploitation décentralisé pour l'agriculture, la robotique et la domotique.**

Pixel OS connecte fermes, robots, capteurs et humains dans un réseau pair-à-pair souverain. Chaque utilisateur possède ses données, ses clés et son infrastructure — aucun cloud central.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Pixel OS Ecosystem                     │
├────────────┬────────────┬──────────────┬────────────────┤
│   Serveur  │   Mobile   │   Robotique  │  Communauté    │
│  pixelos-  │   pixapp   │  pixrobots-  │  Documentation │
│  agricol   │            │  os          │  Forum, Matrix │
└────────────┴────────────┴──────────────┴────────────────┘
```

### 📡 Serveur (`backend/`, `web/`, `api/`)
- API REST + MQTT pour robots et capteurs
- Orchestrateur de missions agricoles
- Base de données temps réel (InfluxDB / SQLite)
- Serveur Matrix optionnel (Conduit) pour la messagerie

### 📱 Applications Mobiles

| App | Description | Stack | Statut |
|-----|-------------|-------|--------|
| **PixOS** | App principale — dashboard, tâches, wallet, DAO, paramètres | Kotlin/Compose | ✅ |
| **PixOS Messenger** | Messagerie décentralisée (Matrix), alertes système, espaces | Kotlin/Compose + Matrix SDK | ✅ |
| **PixOS NOP** | Navigateur Web3 — résolution IPFS, ENS, WebView sécurisé | Kotlin/Compose + Web3j | ✅ |
| **PixConnect** | Contrôle réseau — WiFi, Bluetooth, données, mesh PixNet, firewall | Kotlin/Compose + API système | ✅ |
| **PixOS Livestream** | Streaming live pair-à-pair (WebRTC) — caméras, robots, événements | Kotlin/Compose + WebRTC | 📝 |
| **PixOS Office** | Suite bureautique — Docs, Sheets, Slides, Base (CRDT, collaboratif) | Kotlin/Compose + CRDT | 📝 |
| **PixOS Phone** | Téléphone — GSM + VoIP Matrix, contacts, historique | Kotlin/Compose + TelecomManager | 📝 |

### 🛠️ SDK partagé : `pixcore-android`

Bibliothèque Android mutualisée pour toutes les apps Pixel :

| Module | Fonction |
|--------|----------|
| `PixCore.kt` | Point d'entrée unique — initialisation, mode nœud |
| `RetrofitClient.kt` | Client API REST (OkHttp + token PixKey) |
| `MqttClient.kt` | Client MQTT (Paho — capteurs, robots, alertes) |
| `HeartbeatManager.kt` | Heartbeat UDP (port 9100, 60s) pour le mesh |
| `PixKeyManager.kt` | Gestion des clés Ed25519 (Keystore Android) |
| `WalletManager.kt` | Portefeuille BITROOT (Web3j — Gnosis Chain) |
| `DhtManager.kt` | DHT Kademlia simplifiée (découverte de pairs) |
| `Models.kt` | Modèles partagés (ServerStatus, Task, Sensor, Robot, WalletBalance, Proposal) |

### 🤖 Robotique (`robots/`)
- Firmware ESP32/Arduino pour robots agricoles
- Protocole PixRobots (MQTT + JSON)
- Robots : Inspecteur (surveillance), Moissonneur, Semoir

---

## Démarrage rapide

### Serveur Pixel OS
```bash
git clone https://github.com/pixelsoftwaredesign/pixelos-agricol.git
cd pixelos-agricol
# Lancer le backend
cd backend && docker-compose up -d
```

### Application mobile (PixOS)
```bash
git clone https://github.com/pixelsoftwaredesign/pixelos-agricol.git
cd pixelos-agricol/pixos
./gradlew assembleDebug
```

### Intégrer le SDK dans votre app
```kotlin
// settings.gradle.kts
includeBuild("../pixcore-android")

// build.gradle.kts
implementation("com.pixelos:pixcore-android:1.0.0")

// Initialisation
PixCore.init(context, "https://mon-serveur:8080", "mon-token-pixkey")
```

---

## Principes

- **Souveraineté** — vos données, vos clés, votre infrastructure
- **Pair-à-pair** — pas de cloud, pas de dépendance externe
- **Chiffré** — tout est signé (Ed25519) et chiffré de bout en bout
- **Lightweight** — fonctionne sur des vieux téléphones recyclés
- **Communauté** — open source (MIT), forks bienvenus

---

## Licence

MIT — faites ce que vous voulez, contribuez si le cœur vous en dit.
