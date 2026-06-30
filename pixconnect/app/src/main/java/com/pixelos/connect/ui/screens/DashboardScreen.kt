package com.pixelos.connect.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(onNavigate: (String) -> Unit) {
    Scaffold(
        topBar = { TopAppBar(title = { Text("PixConnect") }) }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
            Text("Réseau & Données", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(16.dp))

            DashboardCard("Wi-Fi", "Gérer les connexions sans fil", Icons.Default.Wifi, onClick = { onNavigate("wifi") })
            Spacer(Modifier.height(8.dp))
            DashboardCard("Bluetooth", "Appairer capteurs et appareils", Icons.Default.Bluetooth, onClick = { onNavigate("bluetooth") })
            Spacer(Modifier.height(8.dp))
            DashboardCard("Données", "Consommation et limites par app", Icons.Default.DataUsage, onClick = { onNavigate("data") })
            Spacer(Modifier.height(8.dp))
            DashboardCard("Mesh PixNet", "Paires, latence, partage", Icons.Default.Hub, onClick = { onNavigate("mesh") })
            Spacer(Modifier.height(8.dp))
            DashboardCard("Firewall", "PixDefend – règles par app", Icons.Default.Shield, onClick = { onNavigate("firewall") })
            Spacer(Modifier.height(8.dp))
            DashboardCard("Profils", "Basculer ferme/maison/champ", Icons.Default.SwapHoriz, onClick = { onNavigate("profiles") })
        }
    }
}

@Composable
fun DashboardCard(title: String, subtitle: String, icon: androidx.compose.ui.graphics.vector.ImageVector, onClick: () -> Unit) {
    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Row(Modifier.padding(16.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
            Icon(icon, null, modifier = Modifier.padding(end = 16.dp), tint = MaterialTheme.colorScheme.primary)
            Column(Modifier.weight(1f)) {
                Text(title, fontWeight = FontWeight.SemiBold)
                Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Icon(Icons.Default.ChevronRight, null)
        }
    }
}
