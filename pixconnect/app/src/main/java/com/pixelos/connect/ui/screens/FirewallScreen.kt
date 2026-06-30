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

data class AppRule(val packageName: String, val appName: String, val blocked: Boolean, val isSystem: Boolean)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FirewallScreen(onBack: () -> Unit) {
    var firewallEnabled by remember { mutableStateOf(false) }
    var blockAds by remember { mutableStateOf(true) }
    var blockSocial by remember { mutableStateOf(false) }
    val apps = remember {
        listOf(
            AppRule("com.pixelos.messenger", "PixOS Messenger", false, false),
            AppRule("com.pixelos.nop", "PixOS NOP", false, false),
            AppRule("com.android.chrome", "Chrome", false, true),
            AppRule("com.google.android.youtube", "YouTube", true, true),
            AppRule("org.telegram.messenger", "Telegram", false, false)
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Firewall PixDefend") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } }
            )
        }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Shield, null, Modifier.padding(end = 8.dp), tint = if (firewallEnabled) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                Text("Protection activée", fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                Switch(checked = firewallEnabled, onCheckedChange = { firewallEnabled = it })
            }
            HorizontalDivider()

            Card(Modifier.fillMaxWidth().padding(16.dp)) {
                Column(Modifier.padding(16.dp)) {
                    Text("Règles globales", fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.height(8.dp))
                    FirewallRuleRow("Bloquer les publicités", blockAds, { blockAds = it })
                    FirewallRuleRow("Bloquer les réseaux sociaux", blockSocial, { blockSocial = it })
                }
            }

            Text("Applications", style = MaterialTheme.typography.labelLarge, modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp))
            LazyColumn {
                items(apps) { app ->
                    Card(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp)) {
                        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Icon(if (app.isSystem) Icons.Default.Build else Icons.Default.Apps, null, Modifier.padding(end = 12.dp), tint = MaterialTheme.colorScheme.primary)
                            Column(Modifier.weight(1f)) {
                                Text(app.appName, fontWeight = FontWeight.Medium)
                                Text(app.packageName, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Switch(checked = app.blocked, onCheckedChange = { /* toggle app rule */ })
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun FirewallRuleRow(label: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, modifier = Modifier.weight(1f))
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}
