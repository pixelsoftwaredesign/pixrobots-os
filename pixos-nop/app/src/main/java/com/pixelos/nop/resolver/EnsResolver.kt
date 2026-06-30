package com.pixelos.nop.resolver

import org.web3j.ens.EnsResolver as Web3jEnsResolver
import org.web3j.protocol.Web3j
import org.web3j.protocol.http.HttpService

object EnsResolver {
    private val web3 = Web3j.build(HttpService("https://ethereum-rpc.publicnode.com"))
    private val resolver = Web3jEnsResolver(web3)

    fun resolve(name: String): String? {
        return try {
            resolver.resolve(name.removeSuffix(".eth") + ".eth")
        } catch (_: Exception) {
            null
        }
    }
}
