package com.pixelos.messenger

import android.app.Application
import com.pixelos.messenger.matrix.MatrixClient

class MessengerApp : Application() {
    override fun onCreate() {
        super.onCreate()
        MatrixClient.init(this)
    }
}
