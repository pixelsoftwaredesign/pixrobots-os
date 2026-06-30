package com.pixelos.sdk.models

data class ServerStatus(
    val status: String = "",
    val version: String = "",
    val uptime: String = "",
    val nodes: Int = 0
)

data class Task(
    val id: String = "",
    val title: String = "",
    val description: String = "",
    val status: String = "pending",
    val priority: String = "normal",
    val assignedTo: String = "",
    val zone: String = "",
    val createdAt: String = "",
    val completedAt: String? = null
)

data class Sensor(
    val id: String = "",
    val nodeId: String = "",
    val type: String = "",
    val value: Double = 0.0,
    val unit: String = "",
    val zone: String = "",
    val battery: Double = 100.0,
    val online: Boolean = false
)

data class Robot(
    val id: String = "",
    val name: String = "",
    val role: String = "",
    val status: String = "idle",
    val battery: Double = 0.0,
    val posX: Double? = null,
    val posY: Double? = null,
    val currentMission: String? = null,
    val online: Boolean = false
)

data class WalletBalance(
    val address: String = "",
    val balance: String = "0",
    val network: String = "gnosis"
)

data class Proposal(
    val id: String = "",
    val title: String = "",
    val description: String = "",
    val creator: String = "",
    val status: String = "active",
    val votesFor: Int = 0,
    val votesAgainst: Int = 0,
    val deadline: String = ""
)

data class VoteRequest(
    val proposalId: String,
    val vote: Boolean
)

data class VoteResponse(
    val success: Boolean = false,
    val message: String = ""
)

data class AuthResponse(
    val token: String = "",
    val success: Boolean = false,
    val message: String = ""
)
