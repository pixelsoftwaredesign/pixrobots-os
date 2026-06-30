package com.pixelos.mobile.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import com.pixelos.sdk.PixCore

@Composable
fun SettingsScreen(nav: NavController) {
    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Text("Paramètres", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(24.dp))
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text("Serveur: ${PixCore.serverUrl}")
                Spacer(Modifier.height(8.dp))
                Text("Mode nœud: ${if (PixCore.nodeMode) "Actif" else "Inactif"}")
                Spacer(Modifier.height(16.dp))
                Button({
                    PixCore.disableNodeMode()
                    nav.navigate("connect") { popUpTo(0) { inclusive = true } }
                }, Modifier.fillMaxWidth()) { Text("Déconnexion") }
            }
        }
    }
}
