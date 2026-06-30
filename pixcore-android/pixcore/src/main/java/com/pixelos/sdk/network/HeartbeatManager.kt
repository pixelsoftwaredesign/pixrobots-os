package com.pixelos.sdk.network

import com.google.gson.Gson
import com.pixelos.sdk.PixCore
import kotlinx.coroutines.*
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress

object HeartbeatManager {
    private var job: Job? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val gson = Gson()
    private const val PORT = 9100
    private const val BROADCAST = "255.255.255.255"

    data class HeartbeatMsg(
        val node_id: String,
        val node_type: String = "android",
        val status: String = "active",
        val battery: Int = 0,
        val timestamp: Long = System.currentTimeMillis()
    )

    fun start() {
        job = scope.launch {
            val socket = DatagramSocket().apply { broadcast = true }
            while (isActive) {
                try {
                    val msg = HeartbeatMsg(
                        node_id = PixCore.context.packageName,
                        battery = getBatteryLevel()
                    )
                    val data = gson.toJson(msg).toByteArray()
                    val packet = DatagramPacket(data, data.size, InetAddress.getByName(BROADCAST), PORT)
                    socket.send(packet)
                } catch (_: Exception) {}
                delay(60_000)
            }
            socket.close()
        }
    }

    fun stop() {
        job?.cancel()
        scope.cancel()
    }

    private fun getBatteryLevel(): Int {
        return try {
            val intent = PixCore.context.registerReceiver(null, android.content.IntentFilter(android.content.Intent.ACTION_BATTERY_CHANGED))
            val level = intent?.getIntExtra(android.os.BatteryManager.EXTRA_LEVEL, -1) ?: -1
            val scale = intent?.getIntExtra(android.os.BatteryManager.EXTRA_SCALE, -1) ?: -1
            if (level > 0 && scale > 0) (level * 100) / scale else -1
        } catch (_: Exception) { -1 }
    }
}
