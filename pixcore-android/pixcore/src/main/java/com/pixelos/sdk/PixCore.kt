package com.pixelos.sdk

import android.content.Context
import com.pixelos.sdk.network.RetrofitClient
import com.pixelos.sdk.network.MqttClient
import com.pixelos.sdk.network.HeartbeatManager
import com.pixelos.sdk.auth.PixKeyManager
import com.pixelos.sdk.wallet.WalletManager
import com.pixelos.sdk.dht.DhtManager

object PixCore {
    lateinit var context: Context
    var serverUrl: String = ""
    var authToken: String = ""
    var nodeMode: Boolean = false

    fun init(appContext: Context, url: String, token: String) {
        context = appContext.applicationContext
        serverUrl = url
        authToken = token
        RetrofitClient.init(url, token)
        MqttClient.init(appContext, url)
        PixKeyManager.init(appContext)
        WalletManager.init()
        if (nodeMode) {
            HeartbeatManager.start()
            DhtManager.start()
        }
    }

    fun enableNodeMode() {
        nodeMode = true
        HeartbeatManager.start()
        DhtManager.start()
    }

    fun disableNodeMode() {
        nodeMode = false
        HeartbeatManager.stop()
        DhtManager.stop()
    }
}
