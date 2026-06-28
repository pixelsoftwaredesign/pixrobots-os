import logging
import random
import time

logger = logging.getLogger(__name__)


class SoilMonitor:
    def __init__(self, config: dict):
        self.pin_moisture = config.get("pin_moisture")
        self.pin_ph = config.get("pin_ph")
        self.pin_npk = config.get("pin_npk")
        self.pin_temp = config.get("pin_temp")
        self.type = config.get("type", "capacitif")
        self._simulated = True

    def lire_humidite(self) -> float:
        try:
            if self._simulated:
                base = random.gauss(45, 15)
                return round(max(0, min(100, base)), 1)
            import RPi.GPIO as GPIO
            import Adafruit_ADS1x15
            adc = Adafruit_ADS1x15.ADS1115()
            raw = adc.read_adc(self.pin_moisture, gain=1)
            return round(100 - (raw / 32767 * 100), 1)
        except Exception as e:
            logger.error(f"Erreur humidité sol: {e}")
            return -1

    def lire_ph(self) -> float:
        try:
            if self._simulated:
                return round(random.gauss(6.8, 0.5), 2)
            import RPi.GPIO as GPIO
            import Adafruit_ADS1x15
            adc = Adafruit_ADS1x15.ADS1115()
            raw = adc.read_adc(self.pin_ph, gain=1)
            voltage = raw / 32767 * 5.0
            ph = 7.0 + ((2.5 - voltage) / 0.18)
            return round(max(0, min(14, ph)), 2)
        except Exception as e:
            logger.error(f"Erreur pH: {e}")
            return -1

    def lire_npk(self) -> dict:
        try:
            if self._simulated:
                return {
                    "azote": round(random.gauss(30, 10), 1),
                    "phosphore": round(random.gauss(20, 8), 1),
                    "potassium": round(random.gauss(40, 12), 1),
                }
            return {"azote": -1, "phosphore": -1, "potassium": -1}
        except Exception as e:
            logger.error(f"Erreur NPK: {e}")
            return {"azote": -1, "phosphore": -1, "potassium": -1}

    def lire_temperature_sol(self) -> float:
        try:
            if self._simulated:
                return round(random.gauss(22, 4), 1)
            return -1
        except Exception as e:
            logger.error(f"Erreur température sol: {e}")
            return -1

    def lire_tout(self) -> dict:
        return {
            "humidite": self.lire_humidite(),
            "ph": self.lire_ph(),
            "npk": self.lire_npk(),
            "temperature_sol": self.lire_temperature_sol(),
        }
