package com.pixelos.connect

import android.app.Application
import com.pixelos.sdk.PixCore

class ConnectApp : Application() {
    override fun onCreate() {
        super.onCreate()
        if (PixCore.authToken.isNotBlank()) {
            PixCore.nodeMode = true
        }
    }
}
