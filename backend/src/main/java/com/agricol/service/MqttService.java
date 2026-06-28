package com.agricol.service;

import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.eclipse.paho.client.mqttv3.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;

@Service
@Slf4j
public class MqttService {

    @Value("${app.mqtt.broker}")
    private String broker;

    @Value("${app.mqtt.client-id}")
    private String clientId;

    @Value("${app.mqtt.topic-prefix}")
    private String topicPrefix;

    private MqttClient client;

    @PostConstruct
    public void init() {
        try {
            client = new MqttClient(broker, clientId);
            MqttConnectOptions opts = new MqttConnectOptions();
            opts.setAutomaticReconnect(true);
            opts.setCleanSession(true);
            opts.setConnectionTimeout(10);
            client.connect(opts);
            log.info("Connecté au broker MQTT: {}", broker);
        } catch (MqttException e) {
            log.error("Erreur connexion MQTT", e);
        }
    }

    public void publier(Long zoneId, boolean ouvrir) {
        String topic = topicPrefix + "vanne/" + zoneId;
        String payload = ouvrir ? "OUVRIR" : "FERMER";

        try {
            MqttMessage message = new MqttMessage(payload.getBytes(StandardCharsets.UTF_8));
            message.setQos(1);
            client.publish(topic, message);
            log.info("MQTT publié sur {}: {}", topic, payload);
        } catch (MqttException e) {
            log.error("Erreur publication MQTT", e);
        }
    }
}
