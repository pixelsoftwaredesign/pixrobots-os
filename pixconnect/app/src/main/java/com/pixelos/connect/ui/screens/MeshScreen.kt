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
import com.pixelos.sdk.PixCore

data class MeshPeer(val id: String, val ip: String, val latency: Int, val signalDb: Int)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MeshScreen(onBack: () -> Unit) {
    var meshEnabled by remember { mutableStateOf(PixCore.nodeMode) }
    val peers = remember {
        listOf(
            MeshPeer("node-f3a8", "10.0.0.42", 12, -65),
            MeshPeer("node-b1c4", "10.0.0.17", 18, -72),
            MeshPeer("node-d9e2", "10.0.0.89", 24, -80)
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Mesh PixNet") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } }
            )
        }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Réseau maillé", fontWeight = FontWeight.Bold)
                    Text("ID: ${PixCore.authToken.take(8)}...", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Switch(checked = meshEnabled, onCheckedChange = { meshEnabled = it; PixCore.nodeMode = it })
            }
            HorizontalDivider()

            if (!meshEnabled) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("Mesh désactivé", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            } else {
                Row(Modifier.padding(16.dp)) {
                    Text("Paires connectées (${peers.size})", style = MaterialTheme.typography.labelLarge)
                    Spacer(Modifier.weight(1f))
                    FilledTonalButton({ /* rafraîchir */ }) { Icon(Icons.Default.Refresh, "Rafraîchir", Modifier.padding(end = 4.dp)); Text("Scan") }
                }

                LazyColumn {
                    items(peers) { peer ->
                        Card(
                            Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
                            elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                        ) {
                            Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.Hub, null, tint = MaterialTheme.colorScheme.primary)
                                Spacer(Modifier.width(12.dp))
                                Column(Modifier.weight(1f)) {
                                    Text(peer.id, fontWeight = FontWeight.Medium)
                                    Text(peer.ip, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                                Column(horizontalAlignment = Alignment.End) {
                                    Text("${peer.latency} ms", fontWeight = FontWeight.Bold, color = if (peer.latency < 15) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.error)
                                    Text("${peer.signalDb} dBm", style = MaterialTheme.typography.bodySmall)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
