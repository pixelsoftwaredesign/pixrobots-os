package com.pixelos.connect.manager

import android.app.usage.NetworkStats
import android.app.usage.NetworkStatsManager
import android.content.Context
import android.net.ConnectivityManager

object DataMonitorManager {
    private var statsManager: NetworkStatsManager? = null

    data class AppUsage(val packageName: String, val appName: String, val rxBytes: Long, val txBytes: Long)

    data class DataStats(val totalRx: Long, val totalTx: Long, val apps: List<AppUsage>)

    fun init(context: Context) {
        statsManager = context.getSystemService(Context.NETWORK_STATS_SERVICE) as? NetworkStatsManager
    }

    fun getCurrentUsage(subscriberId: String?, startTime: Long, endTime: Long): DataStats {
        val apps = mutableListOf<AppUsage>()
        var totalRx = 0L
        var totalTx = 0L

        try {
            val wifiBucket = statsManager?.querySummary(ConnectivityManager.TYPE_WIFI, null, startTime, endTime)
            val mobileBucket = statsManager?.querySummary(ConnectivityManager.TYPE_MOBILE, subscriberId, startTime, endTime)

            listOfNotNull(wifiBucket, mobileBucket).forEach { bucket ->
                var bucketEntry: NetworkStats.Bucket? = null
                while (bucket.hasNextBucket()) {
                    bucketEntry = NetworkStats.Bucket()
                    bucket.getNextBucket(bucketEntry)
                    totalRx += bucketEntry.rxBytes
                    totalTx += bucketEntry.txBytes
                    apps.add(AppUsage(
                        packageName = "uid:${bucketEntry.uid}",
                        appName = "App #${bucketEntry.uid}",
                        rxBytes = bucketEntry.rxBytes,
                        txBytes = bucketEntry.txBytes
                    ))
                }
            }
        } catch (_: Exception) {}

        return DataStats(totalRx = totalRx, totalTx = totalTx, apps = apps.sortedByDescending { it.rxBytes + it.txBytes })
    }
}
