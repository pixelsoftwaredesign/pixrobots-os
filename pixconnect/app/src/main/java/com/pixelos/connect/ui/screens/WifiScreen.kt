package com.pixelos.connect.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pixelos.connect.manager.WifiManager

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WifiScreen(onBack: () -> Unit) {
    var networks by remember { mutableStateOf(WifiManager.startScan()) }
    var wifiEnabled by remember { mutableStateOf(WifiManager.isWifiEnabled()) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Wi-Fi") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } }
            )
        }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Wi-Fi", fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                Switch(
                    checked = wifiEnabled,
                    onCheckedChange = { WifiManager.toggleWifi(it); wifiEnabled = it }
                )
            }
            HorizontalDivider()

            if (!wifiEnabled) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("Wi-Fi désactivé", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            } else {
                Row(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                    Text("Réseaux disponibles", style = MaterialTheme.typography.labelLarge)
                    Spacer(Modifier.weight(1f))
                    IconButton({ networks = WifiManager.startScan() }) { Icon(Icons.Default.Refresh, "Scanner") }
                }
                LazyColumn {
                    items(networks) { network ->
                        Card(
                            Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
                            elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                        ) {
                            Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    when {
                                        network.level > -50 -> Icons.Default.Wifi
                                        network.level > -70 -> Icons.Default.Wifi2Bar
                                        else -> Icons.Default.Wifi1Bar
                                    }, null, tint = MaterialTheme.colorScheme.primary
                                )
                                Spacer(Modifier.width(12.dp))
                                Column(Modifier.weight(1f)) {
                                    Text(network.ssid, fontWeight = FontWeight.Medium)
                                    Text("${network.level} dBm · ${if (network.secured) "Sécurisé" else "Ouvert"}", style = MaterialTheme.typography.bodySmall)
                                }
                                if (network.secured) Icon(Icons.Default.Lock, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
        }
    }
}
