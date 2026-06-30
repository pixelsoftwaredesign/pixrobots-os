package com.pixelos.messenger.matrix

import com.pixelos.sdk.auth.PixKeyManager
import org.matrix.androidsdk.rest.model.login.Credentials

object PixKeyAuthProvider {
    fun createMatrixCredentials(): Credentials? {
        return try {
            val publicKey = PixKeyManager.getPublicKey()
            val userId = PixKeyManager.getUserId()
            if (publicKey == null || userId == null) return null

            Credentials().apply {
                this.accessToken = publicKey
                this.userId = "@$userId:pixelos"
            }
        } catch (_: Exception) {
            null
        }
    }

    fun getMatrixPassword(): String {
        // Le mot de passe Matrix est dérivé de la clé PixKey
        val publicKey = PixKeyManager.getPublicKey() ?: return ""
        return java.util.Base64.getEncoder().encodeToString(publicKey.toByteArray())
    }
}
