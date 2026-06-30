package com.pixelos.sdk.wallet

import org.web3j.crypto.CipherException
import org.web3j.crypto.Credentials
import org.web3j.crypto.WalletUtils
import org.web3j.protocol.Web3j
import org.web3j.protocol.http.HttpService
import org.web3j.utils.Convert
import java.math.BigDecimal

object WalletManager {
    private const val GNOSIS_RPC = "https://rpc.gnosischain.com"
    private var web3: Web3j? = null
    private var credentials: Credentials? = null
    var address: String = ""
        private set

    fun init() {
        web3 = Web3j.build(HttpService(GNOSIS_RPC))
    }

    fun importPrivateKey(privateKey: String) {
        credentials = Credentials.create(privateKey)
        address = credentials!!.address
    }

    fun getBalance(): BigDecimal {
        val addr = address.ifEmpty { return BigDecimal.ZERO }
        return try {
            val wei = web3?.ethGetBalance(addr, org.web3j.protocol.core.DefaultBlockParameterName.LATEST)
                ?.send()?.balance ?: java.math.BigInteger.ZERO
            Convert.fromWei(wei.toString(), Convert.Unit.ETHER)
        } catch (_: Exception) { BigDecimal.ZERO }
    }

    fun isReady(): Boolean = credentials != null
}
