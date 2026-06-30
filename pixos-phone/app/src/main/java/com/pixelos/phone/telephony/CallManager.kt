package com.pixelos.phone.telephony

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.telecom.TelecomManager
import androidx.core.content.ContextCompat

object CallManager {
    data class CallLogEntry(val number: String, val name: String, val type: Int, val date: Long, val duration: Long)

    fun dial(context: Context, number: String) {
        val intent = Intent(Intent.ACTION_CALL, Uri.parse("tel:$number")).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.CALL_PHONE) == PackageManager.PERMISSION_GRANTED) {
            context.startActivity(intent)
        }
    }

    fun isVoipAvailable(number: String): Boolean {
        // Vérifier si le numéro correspond à un contact Pixel (Matrix ID)
        return number.contains("@") || number.endsWith(".pixel")
    }

    fun getCallLog(context: Context): List<CallLogEntry> {
        val entries = mutableListOf<CallLogEntry>()
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CALL_LOG) != PackageManager.PERMISSION_GRANTED) return entries

        val cursor = context.contentResolver.query(
            android.provider.CallLog.Calls.CONTENT_URI, null, null, null,
            "${android.provider.CallLog.Calls.DATE} DESC LIMIT 50"
        )
        cursor?.use {
            val numIdx = it.getColumnIndex(android.provider.CallLog.Calls.NUMBER)
            val nameIdx = it.getColumnIndex(android.provider.CallLog.Calls.CACHED_NAME)
            val typeIdx = it.getColumnIndex(android.provider.CallLog.Calls.TYPE)
            val dateIdx = it.getColumnIndex(android.provider.CallLog.Calls.DATE)
            val durIdx = it.getColumnIndex(android.provider.CallLog.Calls.DURATION)
            while (it.moveToNext()) {
                entries.add(CallLogEntry(
                    number = it.getString(numIdx) ?: "",
                    name = it.getString(nameIdx) ?: "Inconnu",
                    type = it.getInt(typeIdx),
                    date = it.getLong(dateIdx),
                    duration = it.getLong(durIdx)
                ))
            }
        }
        return entries
    }
}
