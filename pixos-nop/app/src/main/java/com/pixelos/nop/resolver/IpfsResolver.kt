package com.pixelos.nop.resolver

import java.net.URL

object IpfsResolver {
    private val gateways = listOf(
        "https://ipfs.io/ipfs/",
        "https://dweb.link/ipfs/",
        "http://localhost:8080/ipfs/"
    )
    private val ipnsGateways = listOf(
        "https://ipfs.io/ipns/",
        "https://dweb.link/ipns/"
    )

    fun resolve(cid: String): String = gateways.first() + cid

    fun resolveIpns(name: String): String = ipnsGateways.first() + name

    fun isIpfsUrl(url: String): Boolean = url.startsWith("ipfs://") || url.startsWith("ipns://")
}
