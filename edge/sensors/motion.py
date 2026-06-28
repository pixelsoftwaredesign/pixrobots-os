import logging
import random
import time

logger = logging.getLogger(__name__)


class MotionDetector:
    def __init__(self, config: dict):
        self.pin_pir = config.get("pin_pir")
        self.pin_ultrasonic_echo = config.get("pin_ultrasonic_echo")
        self.pin_ultrasonic_trig = config.get("pin_ultrasonic_trig")
        self._simulated = True
        self._last_detection = 0

    def detecter_mouvement(self) -> bool:
        try:
            if self._simulated:
                now = time.time()
                if now - self._last_detection > 30:
                    detected = random.random() < 0.08
                    if detected:
                        self._last_detection = now
                    return detected
                return False
            import RPi.GPIO as GPIO
            return GPIO.input(self.pin_pir) == 1
        except Exception as e:
            logger.error(f"Erreur PIR: {e}")
            return False

    def mesurer_distance(self) -> float:
        try:
            if self._simulated:
                return round(random.gauss(200, 50), 1)
            import RPi.GPIO as GPIO
            import time as t
            GPIO.output(self.pin_ultrasonic_trig, True)
            t.sleep(0.00001)
            GPIO.output(self.pin_ultrasonic_trig, False)
            debut = t.time()
            while GPIO.input(self.pin_ultrasonic_echo) == 0:
                debut = t.time()
            fin = t.time()
            while GPIO.input(self.pin_ultrasonic_echo) == 1:
                fin = t.time()
            duree = fin - debut
            distance = (duree * 34300) / 2
            return round(distance, 1)
        except Exception as e:
            logger.error(f"Erreur ultrason: {e}")
            return -1

    def lire_tout(self) -> dict:
        return {
            "mouvement": self.detecter_mouvement(),
            "distance_cm": self.mesurer_distance(),
        }
