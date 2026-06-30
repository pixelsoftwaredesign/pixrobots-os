# Pixel Software Design � Copyright 2026
"""Client MQTT centralisé PixelOS."""

import json
import structlog
import paho.mqtt.client as mqtt
from typing import Callable, Optional


log = structlog.get_logger()


class PixelOSMQTT:
    """Wrapper MQTT avec reconnexion auto, topics structurés."""

    def __init__(self, broker: str = "localhost", port: int = 1883,
                 client_id: str = "pixelos-core"):
        self.broker = broker
        self.port = port
        self.client_id = client_id
        self.client = mqtt.Client(client_id=client_id)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.connected = False
        self.callbacks: dict[str, list[Callable]] = {}
        self._reconnect_delay = 1

    def connect(self) -> None:
        self.client.connect(self.broker, self.port, keepalive=60)
        self.client.loop_start()

    def disconnect(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()

    def publish(self, topic: str, payload: dict, qos: int = 1) -> None:
        self.client.publish(topic, json.dumps(payload), qos=qos)

    def subscribe(self, topic: str, callback: Optional[Callable] = None) -> None:
        self.client.subscribe(topic, qos=1)
        if callback:
            self.callbacks.setdefault(topic, []).append(callback)

    def subscribe_all(self, topics: list[str]) -> None:
        for t in topics:
            self.subscribe(t)

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            self._reconnect_delay = 1
            log.info("MQTT connecté", broker=self.broker, port=self.port)
        else:
            self.connected = False
            log.error("Échec connexion MQTT", rc=rc)

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        log.warning("MQTT déconnecté, reconnexion...", rc=rc)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload)
        except json.JSONDecodeError:
            payload = msg.payload.decode()

        for pattern, cbs in self.callbacks.items():
            if mqtt.topic_matches_sub(pattern, msg.topic):
                for cb in cbs:
                    cb(msg.topic, payload)
