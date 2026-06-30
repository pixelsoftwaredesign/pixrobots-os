package com.pixelos.connect.manager

import android.app.Service
import android.content.Intent
import android.os.IBinder

class DataMonitorService : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // Collecte périodique des stats réseau
        return START_STICKY
    }
}
