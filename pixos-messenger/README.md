# PixOS Messenger

Messagerie décentralisée Pixel OS — basée sur Matrix, chiffrée de bout en bout.

## Fonctionnalités

- Messages directs et groupes
- Espaces publics/privés
- Alertes système automatisées (robots, capteurs)
- Appels audio/vidéo (WebRTC via Matrix)
- Intégration wallet BITROOT
- Notifications via heartbeat (sans Google Play Services)

## Architecture

```
Matrix SDK ← PixKeyAuthProvider (Ed25519 → Matrix ID)
    ├── ChatsScreen       # Liste des discussions
    ├── ChatDetailScreen  # Bulles + saisie
    ├── AlertsScreen      # Alertes système
    ├── SpacesScreen      # Espaces communautaires
    └── SettingsScreen    # Compte, mode nœud
```

## Serveur

Compatible avec tout homeserver Matrix (Synapse, Conduit, Dendrite).
Le serveur Pixel OS peut optionnellement en héberger un.

## Build

```bash
./gradlew assembleDebug
```

## Licence

MIT
