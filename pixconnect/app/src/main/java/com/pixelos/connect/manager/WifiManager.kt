package com.pixelos.connect.manager

import android.content.Context
import android.net.wifi.WifiConfiguration
import android.net.wifi.WifiManager
import android.net.wifi.ScanResult

object WifiManager {
    private var wifiManager: android.net.wifi.WifiManager? = null

    data class WifiNetwork(val ssid: String, val bssid: String, val level: Int, val secured: Boolean)

    fun init(context: Context) {
        wifiManager = context.getSystemService(Context.WIFI_SERVICE) as android.net.wifi.WifiManager
    }

    fun startScan(): List<WifiNetwork> {
        wifiManager?.startScan()
        return wifiManager?.scanResults?.map {
            WifiNetwork(
                ssid = it.SSID,
                bssid = it.BSSID,
                level = it.level,
                secured = it.capabilities.contains("WPA") || it.capabilities.contains("WEP")
            )
        }?.distinctBy { it.ssid }?.filter { it.ssid.isNotBlank() } ?: emptyList()
    }

    fun connect(ssid: String, password: String) {
        val config = WifiConfiguration().apply {
            SSID = "\"$ssid\""
            preSharedKey = "\"$password\""
            allowedKeyManagement.set(WifiConfiguration.KeyMgmt.WPA_PSK)
        }
        val netId = wifiManager?.addNetwork(config)
        netId?.let { wifiManager?.enableNetwork(it, true) }
    }

    fun connectOpen(ssid: String) {
        val config = WifiConfiguration().apply {
            SSID = "\"$ssid\""
            allowedKeyManagement.set(WifiConfiguration.KeyMgmt.NONE)
        }
        val netId = wifiManager?.addNetwork(config)
        netId?.let { wifiManager?.enableNetwork(it, true) }
    }

    fun disconnectCurrent() {
        wifiManager?.disconnect()
    }

    fun isWifiEnabled(): Boolean = wifiManager?.isWifiEnabled ?: false

    fun toggleWifi(enable: Boolean) {
        wifiManager?.isWifiEnabled = enable
    }

    fun createHotspot(ssid: String, password: String) {
        // Nécessite android.net.wifi.WifiManager.LocalOnlyHotspotCallback sur Android 10+
        // Pour l'API 26+, utiliser startLocalOnlyHotspot
    }
}
