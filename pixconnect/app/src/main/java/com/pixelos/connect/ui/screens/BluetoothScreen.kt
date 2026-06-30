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
import com.pixelos.connect.manager.BluetoothManager

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BluetoothScreen(onBack: () -> Unit) {
    var btEnabled by remember { mutableStateOf(BluetoothManager.isEnabled()) }
    var pairedDevices by remember { mutableStateOf(BluetoothManager.getPairedDevices()) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Bluetooth") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } }
            )
        }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Bluetooth", fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                Switch(
                    checked = btEnabled,
                    onCheckedChange = { BluetoothManager.toggle(it); btEnabled = it }
                )
            }
            HorizontalDivider()

            if (!btEnabled) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("Bluetooth désactivé", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            } else {
                Text("Appareils appairés", style = MaterialTheme.typography.labelLarge, modifier = Modifier.padding(16.dp))
                LazyColumn {
                    items(pairedDevices) { device ->
                        Card(
                            Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
                            elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                        ) {
                            Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    when (device.type) {
                                        "Capteur BLE" -> Icons.Default.Sensors
                                        "Audio" -> Icons.Default.Headphones
                                        else -> Icons.Default.Devices
                                    }, null, tint = MaterialTheme.colorScheme.primary
                                )
                                Spacer(Modifier.width(12.dp))
                                Column(Modifier.weight(1f)) {
                                    Text(device.name, fontWeight = FontWeight.Medium)
                                    Text("${device.address} · ${device.type}", style = MaterialTheme.typography.bodySmall)
                                }
                                Icon(Icons.Default.MoreVert, null)
                            }
                        }
                    }
                }

                Spacer(Modifier.height(16.dp))
                Button(
                    onClick = { BluetoothManager.startDiscovery(androidx.compose.ui.platform.LocalContext.current) },
                    modifier = Modifier.padding(horizontal = 16.dp)
                ) {
                    Icon(Icons.Default.Search, null, Modifier.padding(end = 8.dp))
                    Text("Scanner les appareils")
                }
            }
        }
    }
}
