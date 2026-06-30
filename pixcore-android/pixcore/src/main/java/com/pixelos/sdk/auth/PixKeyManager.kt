package com.pixelos.sdk.auth

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.PrivateKey
import java.security.PublicKey

object PixKeyManager {
    private const val KEYSTORE_ALIAS = "pixos_identity"
    private const val ANDROID_KEYSTORE = "AndroidKeyStore"
    private lateinit var keyStore: KeyStore

    fun init(context: Context) {
        keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        getOrCreateKeyPair()
    }

    private fun getOrCreateKeyPair() {
        if (!keyStore.containsAlias(KEYSTORE_ALIAS)) {
            val generator = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, ANDROID_KEYSTORE)
            generator.initialize(
                KeyGenParameterSpec.Builder(KEYSTORE_ALIAS, KeyProperties.PURPOSE_SIGN)
                    .setDigests(KeyProperties.DIGEST_SHA256)
                    .setAlgorithmParameterSpec(java.security.spec.ECGenParameterSpec("secp256k1"))
                    .setUserAuthenticationRequired(false)
                    .build()
            )
            generator.generateKeyPair()
        }
    }

    fun getPublicKey(): PublicKey? {
        return (keyStore.getEntry(KEYSTORE_ALIAS, null) as? KeyStore.PrivateKeyEntry)?.certificate?.publicKey
    }

    fun getPrivateKey(): PrivateKey? {
        return (keyStore.getEntry(KEYSTORE_ALIAS, null) as? KeyStore.PrivateKeyEntry)?.privateKey
    }

    fun nodeId(): String {
        val pub = getPublicKey() ?: return "unknown"
        return pub.hashCode().toUInt().toString(16).padStart(8, '0')
    }
}
