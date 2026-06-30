package com.pixelos.messenger.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.pixelos.sdk.PixCore

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(onBack: () -> Unit) {
    var showDisconnectDialog by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Paramètres") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } }
            )
        }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp)) {
                    ListItem(
                        headlineContent = { Text("Compte") },
                        supportingContent = { Text("Connecté au serveur ${PixCore.serverUrl}") },
                        leadingContent = { Icon(Icons.Default.Person, null) }
                    )
                    HorizontalDivider()
                    ListItem(
                        headlineContent = { Text("Mode nœud") },
                        supportingContent = { Text(if (PixCore.nodeMode) "Activé" else "Désactivé") },
                        leadingContent = { Icon(Icons.Default.Storage, null) }
                    )
                    HorizontalDivider()
                    TextButton({ showDisconnectDialog = true }) { Text("Se déconnecter") }
                }
            }
        }

        if (showDisconnectDialog) {
            AlertDialog(
                onDismissRequest = { showDisconnectDialog = false },
                title = { Text("Déconnexion") },
                text = { Text("Voulez-vous vraiment vous déconnecter ?") },
                confirmButton = { TextButton({ onBack(); showDisconnectDialog = false }) { Text("Oui") } },
                dismissButton = { TextButton({ showDisconnectDialog = false }) { Text("Annuler") } }
            )
        }
    }
}
