import logging
import random
import time

logger = logging.getLogger(__name__)


class WaterMonitor:
    def __init__(self, config: dict):
        self.pin_flow = config.get("pin_flow")
        self.pin_pressure = config.get("pin_pressure")
        self._simulated = True
        self._last_pulse_count = 0
        self._total_liters = 0.0

    def lire_debit(self) -> float:
        try:
            if self._simulated:
                return round(max(0, random.gauss(8, 3)), 2)
            import RPi.GPIO as GPIO
            pulses = self._last_pulse_count
            flow_l_min = pulses / 7.5
            self._last_pulse_count = 0
            return round(flow_l_min, 2)
        except Exception as e:
            logger.error(f"Erreur débit: {e}")
            return -1

    def lire_pression(self) -> float:
        try:
            if self._simulated:
                return round(max(0, random.gauss(2.5, 0.8)), 2)
            import RPi.GPIO as GPIO
            import Adafruit_ADS1x15
            adc = Adafruit_ADS1x15.ADS1115()
            raw = adc.read_adc(self.pin_pressure, gain=1)
            voltage = raw / 32767 * 5.0
            pressure_bar = (voltage - 0.5) / 4.0 * 10
            return round(max(0, pressure_bar), 2)
        except Exception as e:
            logger.error(f"Erreur pression eau: {e}")
            return -1

    def ajouter_consommation(self, litres: float):
        self._total_liters += litres

    def lire_consommation_totale(self) -> float:
        return round(self._total_liters, 1)

    def lire_tout(self) -> dict:
        debit = self.lire_debit()
        return {
            "debit_l_min": debit,
            "pression_bar": self.lire_pression(),
            "consommation_totale_l": self.lire_consommation_totale(),
        }
