import json
import logging
import signal
import sys
import time

import paho.mqtt.client as mqtt
import requests

from config import API_BASE_URL, MQTT_BROKER, MQTT_PORT, INTERVALLE_MESURE_SEC, ZONES
from sensors.soil import SoilMonitor
from sensors.weather import WeatherStation
from sensors.water import WaterMonitor
from sensors.motion import MotionDetector
from sensors.actuator import ActuatorController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("AgriCol.Edge")

ZONE_HANDLERS: dict = {}
MQTT_CLIENT: mqtt.Client | None = None


def initialiser_zones():
    for z in ZONES:
        zone_id = z["id"]
        ZONE_HANDLERS[zone_id] = {
            "config": z,
            "sol": SoilMonitor(z.get("sol", {})),
            "meteo": WeatherStation(z.get("meteo", {})),
            "eau": WaterMonitor(z.get("eau", {})),
            "securite": MotionDetector(z.get("securite", {})),
            "actionneurs": ActuatorController(z.get("actionneurs", {})),
        }
        logger.info(f"Zone {zone_id} ({z['nom']}) initialisée — culture: {z.get('culture', 'N/A')}")


def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode()
    logger.info(f"MQTT ← [{topic}] {payload}")

    for zone_id, h in ZONE_HANDLERS.items():
        if f"vanne/{zone_id}" in topic:
            act = h["actionneurs"]
            if payload == "OUVRIR":
                act.ouvrir_vanne()
            elif payload == "FERMER":
                act.fermer_vanne()
        if f"pompe/{zone_id}" in topic:
            act = h["actionneurs"]
            if payload == "DEMARRER":
                act.demarrer_pompe()
            elif payload == "ARRETER":
                act.arreter_pompe()


def connecter_mqtt():
    global MQTT_CLIENT
    client = mqtt.Client()
    client.on_message = on_message
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.subscribe("agricol/vanne/#")
        client.subscribe("agricol/pompe/#")
        client.loop_start()
        logger.info(f"MQTT connecté à {MQTT_BROKER}:{MQTT_PORT}")
    except Exception as e:
        logger.warning(f"MQTT indisponible, mode dégradé: {e}")
    MQTT_CLIENT = client
    return client


def envoyer_payload(endpoint: str, payload: dict):
    try:
        resp = requests.post(
            f"{API_BASE_URL}/{endpoint}",
            json=payload,
            timeout=15,
        )
        if resp.status_code in (200, 201):
            logger.debug(f"→ {endpoint} OK")
        else:
            logger.warning(f"→ {endpoint} HTTP {resp.status_code}: {resp.text[:100]}")
    except requests.RequestException as e:
        logger.warning(f"→ {endpoint} erreur: {e}")


def publier_mqtt(topic_suffix: str, payload: dict):
    if MQTT_CLIENT:
        topic = f"agricol/{topic_suffix}"
        MQTT_CLIENT.publish(topic, json.dumps(payload))


def boucle_principale():
    logger.info(f"Démarrage — {len(ZONE_HANDLERS)} zones, intervalle {INTERVALLE_MESURE_SEC}s")
    cycle = 0

    while True:
        cycle += 1
        logger.info(f"=== Cycle #{cycle} ===")

        for zone_id, h in ZONE_HANDLERS.items():
            cfg = h["config"]
            nom = cfg["nom"]
            logger.info(f"--- {nom} (zone {zone_id}) ---")

            sol = h["sol"].lire_tout()
            meteo = h["meteo"].lire_tout()
            eau = h["eau"].lire_tout()
            securite = h["securite"].lire_tout()
            act = h["actionneurs"]

            envoyer_payload("mesures", {
                "zoneId": zone_id,
                "humidite": sol["humidite"],
                "temperature": meteo["temperature_air"],
                "conductivite": None,
                "humidite_sol": sol["humidite"],
                "ph_sol": sol["ph"],
                "npk_azote": sol["npk"]["azote"],
                "npk_phosphore": sol["npk"]["phosphore"],
                "npk_potassium": sol["npk"]["potassium"],
                "temperature_sol": sol["temperature_sol"],
                "temperature_air": meteo["temperature_air"],
                "humidite_air": meteo["humidite_air"],
                "pression": meteo["pression"],
                "pluie": meteo["pluie"],
                "vent_kmh": meteo["vent_kmh"],
                "luminosite_lux": meteo["luminosite_lux"],
                "debit_eau_l_min": eau["debit_l_min"],
                "pression_eau_bar": eau["pression_bar"],
            })

            if securite["mouvement"]:
                logger.warning(f"⚠ Mouvement détecté dans {nom}!")
                publier_mqtt(f"alerte/{zone_id}", {
                    "type": "mouvement",
                    "zone": nom,
                    "distance_cm": securite["distance_cm"],
                    "timestamp": time.time(),
                })

            if eau["debit_l_min"] > 0 and act.etat_vanne():
                conso = eau["debit_l_min"] * (INTERVALLE_MESURE_SEC / 60)
                h["eau"].ajouter_consommation(conso)
                logger.info(f"  💧 Consommation: +{conso:.1f}L (total: {eau['consommation_totale_l']:.1f}L)")

            vanne_état = "OUVERTE" if act.etat_vanne() else "FERMÉE"
            pompe_état = "ACTIVE" if act.etat_pompe() else "ARRÊTÉE"
            logger.info(
                f"  🌱 Sol: {sol['humidite']:.0f}% | pH: {sol['ph']} | "
                f"🌤 {meteo['temperature_air']:.0f}°C {meteo['humidite_air']:.0f}% | "
                f"🚿 Vanne: {vanne_état} | Pompe: {pompe_état}"
            )

        logger.info(f"Pause {INTERVALLE_MESURE_SEC}s...\n")
        time.sleep(INTERVALLE_MESURE_SEC)


def arreter(sig, frame):
    logger.info("Arrêt du système AgriCol Edge...")
    for zone_id, h in ZONE_HANDLERS.items():
        act = h["actionneurs"]
        if act.etat_vanne():
            act.fermer_vanne()
            logger.info(f"Vanne zone {zone_id} fermée (sécurité)")
        if act.etat_pompe():
            act.arreter_pompe()
    if MQTT_CLIENT:
        MQTT_CLIENT.loop_stop()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, arreter)
    signal.signal(signal.SIGTERM, arreter)
    logger.info("=" * 50)
    logger.info("AgriCol — Système Edge Intelligent")
    logger.info("=" * 50)

    initialiser_zones()
    connecter_mqtt()
    boucle_principale()
