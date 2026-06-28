import logging

logger = logging.getLogger(__name__)


class ActuatorController:
    def __init__(self, config: dict):
        self.pin_vanne = config.get("pin_vanne")
        self.pin_pompe = config.get("pin_pompe")
        self._simulated = True
        self._vanne_ouverte = False
        self._pompe_active = False

    def ouvrir_vanne(self) -> bool:
        try:
            if self._simulated:
                self._vanne_ouverte = True
                logger.info(f"[SIMUL] Vanne {self.pin_vanne} OUVERTE")
                return True
            import RPi.GPIO as GPIO
            GPIO.output(self.pin_vanne, GPIO.HIGH)
            self._vanne_ouverte = True
            return True
        except Exception as e:
            logger.error(f"Erreur ouverture vanne: {e}")
            return False

    def fermer_vanne(self) -> bool:
        try:
            if self._simulated:
                self._vanne_ouverte = False
                logger.info(f"[SIMUL] Vanne {self.pin_vanne} FERMEE")
                return True
            import RPi.GPIO as GPIO
            GPIO.output(self.pin_vanne, GPIO.LOW)
            self._vanne_ouverte = False
            return True
        except Exception as e:
            logger.error(f"Erreur fermeture vanne: {e}")
            return False

    def etat_vanne(self) -> bool:
        return self._vanne_ouverte

    def demarrer_pompe(self) -> bool:
        try:
            if self._simulated:
                self._pompe_active = True
                logger.info(f"[SIMUL] Pompe {self.pin_pompe} DÉMARRÉE")
                return True
            import RPi.GPIO as GPIO
            GPIO.output(self.pin_pompe, GPIO.HIGH)
            self._pompe_active = True
            return True
        except Exception as e:
            logger.error(f"Erreur démarrage pompe: {e}")
            return False

    def arreter_pompe(self) -> bool:
        try:
            if self._simulated:
                self._pompe_active = False
                logger.info(f"[SIMUL] Pompe {self.pin_pompe} ARRÊTÉE")
                return True
            import RPi.GPIO as GPIO
            GPIO.output(self.pin_pompe, GPIO.LOW)
            self._pompe_active = False
            return True
        except Exception as e:
            logger.error(f"Erreur arrêt pompe: {e}")
            return False

    def etat_pompe(self) -> bool:
        return self._pompe_active
