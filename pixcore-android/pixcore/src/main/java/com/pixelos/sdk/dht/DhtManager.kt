package com.pixelos.sdk.dht

import kotlinx.coroutines.*
import java.util.concurrent.ConcurrentHashMap

data class Peer(
    val id: String,
    val ip: String,
    val port: Int = 9100,
    var lastSeen: Long = System.currentTimeMillis()
)

object DhtManager {
    private val peers = ConcurrentHashMap<String, Peer>()
    private var job: Job? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private const val PEER_TIMEOUT = 300_000L
    const val REPLICATION = 3
    const val MAX_BUCKET = 8

    fun start() {
        job = scope.launch {
            while (isActive) {
                val now = System.currentTimeMillis()
                peers.values.removeAll { now - it.lastSeen > PEER_TIMEOUT }
                delay(60_000)
            }
        }
    }

    fun stop() {
        job?.cancel()
        peers.clear()
    }

    fun addPeer(id: String, ip: String, port: Int = 9100) {
        val existing = peers[id]
        if (existing != null) {
            peers[id] = existing.copy(lastSeen = System.currentTimeMillis())
        } else if (peers.size < MAX_BUCKET) {
            peers[id] = Peer(id, ip, port)
        }
    }

    fun findClosest(targetId: String, count: Int = REPLICATION): List<Peer> {
        return peers.values
            .sortedBy { it.id.hashCode() xor targetId.hashCode() }
            .take(count)
    }

    fun getAlivePeers(): List<Peer> = peers.values.toList()

    fun peerCount(): Int = peers.size
}
