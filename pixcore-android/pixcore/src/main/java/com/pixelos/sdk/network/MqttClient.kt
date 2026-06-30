package com.pixelos.sdk.network

import android.content.Context
import org.eclipse.paho.android.service.MqttAndroidClient
import org.eclipse.paho.client.mqttv3.*
import org.eclipse.paho.client.mqttv3.persist.MemoryPersistence

object MqttClient {
    private var client: MqttAndroidClient? = null
    private val callbacks = mutableListOf<(String, String) -> Unit>()

    fun init(context: Context, serverUrl: String) {
        val uri = serverUrl
            .replace("http://", "tcp://")
            .replace("https://", "ssl://")
            .replace(":8080", ":1883")
            .replace(":443", ":8883")

        val clientId = "pixos-${android.os.Build.MODEL}-${System.currentTimeMillis()}"
        client = MqttAndroidClient(context, uri, clientId, MemoryPersistence())

        val opts = MqttConnectOptions().apply {
            isAutomaticReconnect = true
            keepAliveInterval = 30
            cleanSession = true
        }

        client?.setCallback(object : MqttCallbackExtended {
            override fun connectComplete(reconnect: Boolean, serverURI: String) {
                subscribe("sensors/#", "robots/+/status", "alerts/#")
            }
            override fun connectionLost(cause: Throwable?) {}
            override fun messageArrived(topic: String?, message: MqttMessage?) {
                if (topic != null && message != null) {
                    callbacks.forEach { it(topic, String(message.payload)) }
                }
            }
            override fun deliveryComplete(token: IMqttDeliveryToken?) {}
        })

        try { client?.connect(opts) } catch (_: Exception) {}
    }

    fun subscribe(vararg topics: String) {
        topics.forEach { topic ->
            try { client?.subscribe(topic, 1) } catch (_: Exception) {}
        }
    }

    fun publish(topic: String, payload: String, qos: Int = 1) {
        try {
            client?.publish(topic, MqttMessage(payload.toByteArray()).apply { this.qos = qos })
        } catch (_: Exception) {}
    }

    fun onMessage(cb: (String, String) -> Unit) {
        callbacks.add(cb)
    }

    fun disconnect() {
        try { client?.disconnect(); client?.close() } catch (_: Exception) {}
    }
}
