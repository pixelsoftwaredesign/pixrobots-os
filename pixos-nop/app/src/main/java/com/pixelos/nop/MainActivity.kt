package com.pixelos.nop

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import android.webkit.WebView
import android.webkit.WebViewClient
import com.pixelos.nop.resolver.IpfsResolver
import com.pixelos.nop.resolver.EnsResolver

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { NopBrowser() }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NopBrowser() {
    var url by remember { mutableStateOf("https://pixelos.org") }
    var webView by remember { mutableStateOf<WebView?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("PixOS NOP") },
                actions = {
                    TextButton({ url = "https://pixelos.org"; webView?.loadUrl(url) }) { Text("Accueil") }
                    TextButton({ url = "ipfs://Qm..."; webView?.loadUrl(IpfsResolver.resolve("Qm...")) }) { Text("IPFS") }
                }
            )
        }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            OutlinedTextField(
                value = url,
                onValueChange = { url = it },
                modifier = Modifier.fillMaxWidth().padding(8.dp),
                singleLine = true,
                trailingIcon = {
                    TextButton({
                        val resolved = resolveUrl(url)
                        webView?.loadUrl(resolved)
                    }) { Text("GO") }
                }
            )

            AndroidView(
                factory = { ctx ->
                    WebView(ctx).apply {
                        settings.javaScriptEnabled = true
                        settings.domStorageEnabled = true
                        settings.loadWithOverviewMode = true
                        settings.useWideViewPort = true
                        webViewClient = object : WebViewClient() {
                            override fun onPageFinished(view: WebView?, loadedUrl: String?) {
                                url = loadedUrl ?: url
                            }
                        }
                        loadUrl(url)
                        webView = this
                    }
                },
                modifier = Modifier.fillMaxSize()
            )
        }
    }
}

fun resolveUrl(input: String): String {
    return when {
        input.startsWith("ipfs://") -> IpfsResolver.resolve(input.removePrefix("ipfs://"))
        input.startsWith("ens://") || input.endsWith(".eth") -> {
            val name = input.removePrefix("ens://").removeSuffix(".eth")
            EnsResolver.resolve(name) ?: input
        }
        input.startsWith("ipns://") -> IpfsResolver.resolveIpns(input.removePrefix("ipns://"))
        !input.startsWith("http://") && !input.startsWith("https://") -> "https://$input"
        else -> input
    }
}
