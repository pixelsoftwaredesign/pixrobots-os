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
import com.pixelos.connect.manager.DataMonitorManager

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DataScreen(onBack: () -> Unit) {
    val usage = remember {
        val now = System.currentTimeMillis()
        DataMonitorManager.getCurrentUsage(null, now - 86400000, now)
    }
    var dataLimit by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Données") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } }
            )
        }
    ) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).padding(horizontal = 16.dp)) {
            item {
                Spacer(Modifier.height(8.dp))
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("Aujourd'hui", style = MaterialTheme.typography.labelLarge)
                        Spacer(Modifier.height(8.dp))
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Icon(Icons.Default.ArrowDownward, null, tint = MaterialTheme.colorScheme.primary)
                                Text(formatBytes(usage.totalRx), fontWeight = FontWeight.Bold)
                                Text("Reçu", style = MaterialTheme.typography.bodySmall)
                            }
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Icon(Icons.Default.ArrowUpward, null, tint = MaterialTheme.colorScheme.error)
                                Text(formatBytes(usage.totalTx), fontWeight = FontWeight.Bold)
                                Text("Envoyé", style = MaterialTheme.typography.bodySmall)
                            }
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Icon(Icons.Default.Total, null, tint = MaterialTheme.colorScheme.secondary)
                                Text(formatBytes(usage.totalRx + usage.totalTx), fontWeight = FontWeight.Bold)
                                Text("Total", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }
                Spacer(Modifier.height(12.dp))

                Text("Limite de données", style = MaterialTheme.typography.labelLarge)
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = dataLimit,
                        onValueChange = { dataLimit = it },
                        modifier = Modifier.weight(1f),
                        label = { Text("Mo par jour") },
                        singleLine = true
                    )
                    Spacer(Modifier.width(8.dp))
                    Button({ /* définir limite */ }) { Text("Appliquer") }
                }
                Spacer(Modifier.height(12.dp))

                Text("Consommation par application", style = MaterialTheme.typography.labelLarge)
                Spacer(Modifier.height(8.dp))
            }

            items(usage.apps.take(20)) { app ->
                Card(Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(app.appName, style = MaterialTheme.typography.bodyMedium)
                            Text(
                                "RX: ${formatBytes(app.rxBytes)} · TX: ${formatBytes(app.txBytes)}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        Text(formatBytes(app.rxBytes + app.txBytes), fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}

private fun formatBytes(bytes: Long): String {
    return when {
        bytes < 1024 -> "$bytes o"
        bytes < 1024 * 1024 -> "${bytes / 1024} Ko"
        else -> "%.1f Mo".format(bytes.toDouble() / (1024 * 1024))
    }
}
