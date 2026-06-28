# Câblage et infrastructure physique

## RS485 (bus filaire capteurs/vannes)

**Caractéristiques :**
- Paire torsadée blindée 2x0.5mm² (Belden 9841 ou équivalent)
- Impédance 120Ω
- Terminaison 120Ω aux deux extrémités du bus
- Distance max : 1.2 km à 9600 bauds
- Topologie : bus linéaire (pas d'étoile)
- Connecteurs : bornier à vis étanche IP65

**Câblage :**
```
OpenBSD         Capteur #10      Capteur #11      Vanne #30
┌──────┐       ┌──────────┐     ┌──────────┐     ┌──────────┐
│USB-   │───┬───│RS485     │──┬──│RS485     │──┬──│RS485     │
│RS485 │   │   │shield    │  │  │shield    │  │  │shield    │
│conver│   │   └──────────┘  │  └──────────┘  │  └──────────┘
└──────┘   │                │                │
        120Ω               ⋮               120Ω
      terminaison        (max 32 nœuds)  terminaison
```

**Alimentation :**
- Bus RS485 : auto-alimenté via USB du convertisseur
- Capteurs Arduino : batterie Li-ion 7.4V + panneau solaire 5W
- Vannes ESP32 : 12V DC depuis bloc d'alimentation central
- Station météo : batterie 18650 + panneau solaire 10W

## Wi-Fi (ESP32)

| Bande   | SSID          | Canal | Puissance | Portée |
|---------|---------------|-------|-----------|--------|
| 2.4 GHz | AgriCol-IoT   | 6     | 20 dBm    | ~100m  |

- Point d'accès dédié 2.4 GHz seulement (pas 5 GHz, portée réduite)
- ESP32 en mode station (pas AP)
- QoS activé pour MQTT (priorité aux commandes vannes)

## Électricité

| Appareil        | Tension | Consommation | Alimentation          |
|-----------------|---------|--------------|-----------------------|
| Mini PC OpenBSD | 12V     | 15-25W       | Secteur ~220VAC       |
| Raspberry Pi    | 5V      | 3-5W         | PoE secteur           |
| ESP32 vanne     | 12V     | 2W (vanne)   | Bloc 12V central      |
| Arduino Mega    | 7.4V    | 1W           | Batterie + solaire    |
| Vanne motorisée | 12V     | 5W (pointe)  | Bloc 12V central      |
| Pompe 12V       | 12V     | 30-60W       | Bloc 12V 10A          |
| Station météo   | 3.7V    | 0.5W         | Batterie + solaire    |

**Bloc alimentation central :**
- Entrée : 220VAC
- Sortie 12VDC 10A (vannes + pompe + ESP32)
- Protection surtension + batterie secourue 12V 7Ah
