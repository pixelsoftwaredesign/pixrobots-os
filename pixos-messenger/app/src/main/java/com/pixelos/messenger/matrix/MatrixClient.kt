package com.pixelos.messenger.matrix

import android.content.Context
import com.pixelos.messenger.ui.screens.AlertMessage
import com.pixelos.messenger.ui.screens.ChatPreview
import com.pixelos.messenger.ui.screens.Message
import com.pixelos.messenger.ui.screens.Space
import com.pixelos.sdk.PixCore
import com.pixelos.sdk.auth.PixKeyManager
import org.matrix.androidsdk.MXSession
import org.matrix.androidsdk.data.Room
import org.matrix.androidsdk.rest.model.Event
import org.matrix.androidsdk.rest.model.message.MessageUtils

object MatrixClient {
    private var session: MXSession? = null
    private val chatPreviews = mutableListOf<ChatPreview>()
    private val messages = mutableMapOf<String, MutableList<Message>>()
    private val alerts = mutableListOf<AlertMessage>()
    private val spaces = mutableListOf<Space>()

    fun init(context: Context) {
        if (PixCore.authToken.isNotBlank()) {
            connect(PixCore.serverUrl, PixCore.authToken)
        }
    }

    fun connect(homeserverUrl: String, accessToken: String) {
        // Connexion Matrix avec le token PixKey comme access token
        // Le homeserver Matrix est dérivé de l'URL du serveur Pixel
        val hsUrl = homeserverUrl.replace(":8080", ":8448")
        try {
            // En production, utiliser MXSession avec les credentials PixKey
            // val credentials = org.matrix.androidsdk.rest.model.login.Credentials()
            // credentials.accessToken = accessToken
            // credentials.userId = "@${PixKeyManager.getUserId()}:pixelos"
            // session = MXSession(context, credentials, hsUrl)
        } catch (_: Exception) {
            // Fallback: données simulées pour le développement
            loadMockData()
        }
    }

    fun createRoom(name: String) {
        // session?.createRoom(name, null, null, null, null)
    }

    fun sendMessage(roomId: String, body: String) {
        val msg = Message("msg-${System.currentTimeMillis()}", "Moi", body, true)
        messages.getOrPut(roomId) { mutableListOf() }.add(msg)
    }

    fun getChatPreviews(): List<ChatPreview> = chatPreviews

    fun getMessages(roomId: String): List<Message> = messages[roomId] ?: emptyList()

    fun getRoomName(roomId: String): String = chatPreviews.find { it.roomId == roomId }?.name ?: roomId

    fun getAlerts(): List<AlertMessage> = alerts

    fun getSpaces(): List<Space> = spaces

    private fun loadMockData() {
        chatPreviews.addAll(listOf(
            ChatPreview("room1", "Serre Nord", "Capteur #3 : humidité 72%", 2),
            ChatPreview("room2", "DevRobots", "Jean: test terminé ✓", 0),
            ChatPreview("room3", "Ferme Pixel", "Bienvenue à tous !", 1),
            ChatPreview("room4", "Marché BITROOT", "Nouveau lot disponible", 5)
        ))
        messages["room1"] = mutableListOf(
            Message("m1", "Robot #1", "Inspection terminée, serre nord OK", false),
            Message("m2", "Capteur #3", "Humidité : 72%, Temp : 24°C", false),
            Message("m3", "Moi", "Parfait, merci", true)
        )
        alerts.addAll(listOf(
            AlertMessage("a1", "Robot #2 HS", "Le robot Inspecteur #2 ne répond plus. Vérification urgente.", "haute"),
            AlertMessage("a2", "Niveau batterie bas", "Station météo : batterie à 12%, remplacer avant 48h.", "moyenne"),
            AlertMessage("a3", "Mise à jour disponible", "Pixel OS v2.1.0 disponible pour votre serveur.", "basse")
        ))
        spaces.addAll(listOf(
            Space("sp1", "Ferme Principale", 12, false),
            Space("sp2", "Communauté Pixel", 248, true),
            Space("sp3", "Dev Team", 8, false)
        ))
    }
}
