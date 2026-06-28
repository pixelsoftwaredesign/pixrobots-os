import logging
import random
import time

logger = logging.getLogger(__name__)


class WeatherStation:
    def __init__(self, config: dict):
        self.pin_dht = config.get("pin_dht")
        self.pin_bmp = config.get("pin_bmp_scl"), config.get("pin_bmp_sda")
        self.pin_rain = config.get("pin_rain")
        self.pin_wind = config.get("pin_wind")
        self.pin_light = config.get("pin_light")
        self._simulated = True

    def lire_air_temp_hum(self) -> tuple:
        try:
            if self._simulated:
                base_temp = random.gauss(28, 5)
                base_hum = random.gauss(60, 15)
                return round(max(-10, min(50, base_temp)), 1), round(max(0, min(100, base_hum)), 1)
            import Adafruit_DHT
            hum, temp = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, self.pin_dht)
            return round(temp, 1), round(hum, 1)
        except Exception as e:
            logger.error(f"Erreur DHT22: {e}")
            return -1, -1

    def lire_pression(self) -> float:
        try:
            if self._simulated:
                return round(random.gauss(1013, 10), 1)
            return 1013.0
        except Exception as e:
            logger.error(f"Erreur BMP280: {e}")
            return -1

    def lire_pluie(self) -> bool:
        try:
            if self._simulated:
                return random.random() < 0.15
            import RPi.GPIO as GPIO
            return GPIO.input(self.pin_rain) == 0
        except Exception as e:
            logger.error(f"Erreur pluie: {e}")
            return False

    def lire_vent(self) -> float:
        try:
            if self._simulated:
                return round(max(0, random.gauss(8, 5)), 1)
            return 0.0
        except Exception as e:
            logger.error(f"Erreur vent: {e}")
            return -1

    def lire_luminosite(self) -> float:
        try:
            if self._simulated:
                heure = time.localtime().tm_hour
                if 6 <= heure <= 18:
                    return round(random.gauss(40000, 15000), 0)
                return round(random.gauss(50, 30), 0)
            import RPi.GPIO as GPIO
            import Adafruit_ADS1x15
            adc = Adafruit_ADS1x15.ADS1115()
            raw = adc.read_adc(self.pin_light, gain=1)
            return round(raw / 32767 * 100000, 0)
        except Exception as e:
            logger.error(f"Erreur luminosité: {e}")
            return -1

    def lire_tout(self) -> dict:
        temp, hum = self.lire_air_temp_hum()
        return {
            "temperature_air": temp,
            "humidite_air": hum,
            "pression": self.lire_pression(),
            "pluie": self.lire_pluie(),
            "vent_kmh": self.lire_vent(),
            "luminosite_lux": self.lire_luminosite(),
        }
