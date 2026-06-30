# AgriculApp — Build

## Prérequis
- Flutter SDK 3.16+
- Android SDK (API 34+) + NDK 27
- JDK 17+

## Build APK
```bash
cd mobile
flutter pub get
flutter build apk --debug        # APK de debug
flutter build apk --release      # APK de production (nécessite signing)
```

L'APK sera dans `mobile/build/app/outputs/flutter-apk/`.

## Installer sur téléphone
```bash
flutter install
# ou
adb install build/app/outputs/flutter-apk/app-debug.apk
```

## Structure
```
mobile/
├── lib/
│   ├── main.dart                 # Point d'entrée + providers
│   ├── models/                   # Modèles de données
│   │   ├── espace.dart, zone.dart, mesure.dart
│   │   ├── sensor.dart, robot.dart, mission.dart, alert.dart
│   ├── services/
│   │   ├── api_service.dart      # Client REST Pixel OS
│   │   ├── mqtt_service.dart     # Client MQTT temps réel
│   │   └── auth_service.dart     # Authentification PixKey
│   ├── providers/
│   │   ├── auth_provider.dart
│   │   ├── sensors_provider.dart
│   │   ├── robots_provider.dart
│   │   └── alerts_provider.dart
│   ├── screens/
│   │   ├── login_screen.dart     # Connexion au serveur Pixel OS
│   │   ├── dashboard_screen.dart # Vue d'ensemble + onglets
│   │   ├── zones_screen.dart     # Gestion des espaces/zones
│   │   ├── missions_screen.dart  # Missions robots
│   │   └── settings_screen.dart  # Paramètres
│   └── widgets/
│       ├── sensor_card.dart
│       ├── robot_card.dart
│       └── humidity_chart.dart
└── pubspec.yaml
```
