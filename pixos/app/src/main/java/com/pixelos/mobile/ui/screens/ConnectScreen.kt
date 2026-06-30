package com.pixelos.mobile.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import com.pixelos.sdk.PixCore
import com.pixelos.sdk.network.RetrofitClient
import kotlinx.coroutines.launch

@Composable
fun ConnectScreen(nav: NavController) {
    var serverUrl by remember { mutableStateOf("http://192.168.1.100:8080") }
    var token by remember { mutableStateOf("") }
    var loading by remember { mutableStateOf(false) }
    var errorMsg by remember { mutableStateOf<String?>(null) }
    var nodeMode by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    Column(
        Modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text("PixOS", style = MaterialTheme.typography.headlineLarge)
        Text("Pixel OS Mobile", style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.height(48.dp))

        OutlinedTextField(serverUrl, { serverUrl = it }, label = { Text("Serveur Pixel OS") }, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(token, { token = it }, label = { Text("Token d'authentification") }, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(12.dp))

        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(nodeMode, { nodeMode = it })
            Text("Activer le mode nœud (contribution au réseau)")
        }

        Spacer(Modifier.height(24.dp))

        Button(
            onClick = {
                scope.launch {
                    loading = true
                    errorMsg = null
                    try {
                        PixCore.init(PixCore.context, serverUrl, token)
                        PixCore.nodeMode = nodeMode
                        val status = RetrofitClient.api.getServerStatus()
                        if (status.isSuccessful) {
                            nav.navigate("dashboard") { popUpTo("connect") { inclusive = true } }
                        } else {
                            errorMsg = "Erreur serveur: ${status.code()}"
                        }
                    } catch (e: Exception) {
                        errorMsg = "Connexion impossible: ${e.message}"
                    }
                    loading = false
                }
            },
            enabled = !loading,
            modifier = Modifier.fillMaxWidth().height(50.dp)
        ) { Text(if (loading) "Connexion..." else "Se connecter") }

        errorMsg?.let {
            Spacer(Modifier.height(12.dp))
            Text(it, color = MaterialTheme.colorScheme.error)
        }
    }
}
