import os
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://192.168.1.100:8080/api")
MQTT_BROKER = os.getenv("MQTT_BROKER", "192.168.1.100")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
INTERVALLE_MESURE_SEC = int(os.getenv("INTERVALLE_MESURE_SEC", "60"))

ZONES = [
    {
        "id": 1,
        "nom": "Serre Nord",
        "culture": "Tomates",
        "sol": {
            "pin_moisture": 0,
            "pin_ph": 1,
            "pin_npk": 2,
            "pin_temp": 17,
            "type": "capacitif",
        },
        "meteo": {
            "pin_dht": 4,
            "pin_bmp_scl": 3,
            "pin_bmp_sda": 2,
            "pin_rain": 27,
            "pin_wind": 22,
            "pin_light": 3,
        },
        "eau": {
            "pin_flow": 5,
            "pin_pressure": 4,
        },
        "securite": {
            "pin_pir": 6,
            "pin_ultrasonic_echo": 20,
            "pin_ultrasonic_trig": 21,
        },
        "actionneurs": {
            "pin_vanne": 18,
            "pin_pompe": 23,
        },
    },
    {
        "id": 2,
        "nom": "Champ Ouest",
        "culture": "Laitue",
        "sol": {
            "pin_moisture": 0,
            "pin_ph": 1,
            "pin_npk": 2,
            "pin_temp": 17,
            "type": "resistif",
        },
        "meteo": {
            "pin_dht": 4,
            "pin_bmp_scl": 3,
            "pin_bmp_sda": 2,
            "pin_rain": 27,
            "pin_wind": 22,
            "pin_light": 3,
        },
        "eau": {
            "pin_flow": 5,
            "pin_pressure": 4,
        },
        "securite": {
            "pin_pir": 6,
            "pin_ultrasonic_echo": 20,
            "pin_ultrasonic_trig": 21,
        },
        "actionneurs": {
            "pin_vanne": 24,
            "pin_pompe": 25,
        },
    },
    {
        "id": 3,
        "nom": "Verger Est",
        "culture": "Pommes",
        "sol": {
            "pin_moisture": 0,
            "pin_ph": 1,
            "pin_npk": 2,
            "pin_temp": 17,
            "type": "capacitif",
        },
        "meteo": {
            "pin_dht": 4,
            "pin_bmp_scl": 3,
            "pin_bmp_sda": 2,
            "pin_rain": 27,
            "pin_wind": 22,
            "pin_light": 3,
        },
        "eau": {
            "pin_flow": 5,
            "pin_pressure": 4,
        },
        "securite": {
            "pin_pir": 6,
            "pin_ultrasonic_echo": 20,
            "pin_ultrasonic_trig": 21,
        },
        "actionneurs": {
            "pin_vanne": 26,
            "pin_pompe": 27,
        },
    },
]

try:
    import json as _json
    _extra = os.getenv("ZONES_EXTRA")
    if _extra:
        ZONES.extend(_json.loads(_extra))
except Exception:
    pass
