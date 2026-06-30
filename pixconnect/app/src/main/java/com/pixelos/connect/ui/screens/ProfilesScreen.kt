package com.pixelos.connect.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pixelos.connect.data.NetworkProfile

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfilesScreen(onBack: () -> Unit) {
    val profiles = remember {
        listOf(
            NetworkProfile("Ferme", "PixelFarm-5G", "********", true, true, 500),
            NetworkProfile("Maison", "Freebox-Ultra", "********", false, false, 1000),
            NetworkProfile("Champ Sud", "AgriMesh-2.4", "********", true, true, 200)
        )
    }
    var activeProfile by remember { mutableStateOf("Ferme") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Profils réseau") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } }
            )
        }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            Text("Basculer entre configurations", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp), color = MaterialTheme.colorScheme.onSurfaceVariant)

            profiles.forEach { profile ->
                val isActive = profile.name == activeProfile
                Card(
                    onClick = { activeProfile = profile.name },
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
                    colors = CardDefaults.cardColors(containerColor = if (isActive) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface),
                    elevation = CardDefaults.cardElevation(defaultElevation = if (isActive) 4.dp else 1.dp)
                ) {
                    Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            if (isActive) Icons.Default.RadioButtonChecked else Icons.Default.RadioButtonUnchecked,
                            null,
                            tint = if (isActive) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(profile.name, fontWeight = FontWeight.Bold)
                            Text("SSID: ${profile.ssid}", style = MaterialTheme.typography.bodySmall)
                            Text("Mesh: ${if (profile.meshEnabled) "Oui" else "Non"} · Limite: ${profile.dataLimitMb} Mo/j", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        if (isActive) {
                            AssistChip(onClick = { /* modifier */ }, label = { Text("Actif") })
                        }
                    }
                }
            }

            Spacer(Modifier.height(16.dp))
            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
                OutlinedButton({ /* ajouter profil */ }, Modifier.weight(1f)) { Icon(Icons.Default.Add, null, Modifier.padding(end = 4.dp)); Text("Nouveau profil") }
                Spacer(Modifier.width(8.dp))
                Button({ /* synchroniser */ }) { Icon(Icons.Default.Sync, null, Modifier.padding(end = 4.dp)); Text("Sync serveur") }
            }
        }
    }
}
