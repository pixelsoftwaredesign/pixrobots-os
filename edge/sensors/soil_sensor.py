import time
import random


def lire_humidite(pin):
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.IN)
        valeur = GPIO.input(pin)
        return round((1 - valeur / 1024) * 100, 1)
    except ImportError:
        return round(random.uniform(20, 80), 1)


def lire_temperature(pin):
    try:
        import Adafruit_DHT
        humidite, temperature = Adafruit_DHT.read_retry(
            Adafruit_DHT.DHT22, pin)
        if humidite is not None:
            return round(temperature, 1)
        return None
    except ImportError:
        return round(random.uniform(15, 35), 1)
