package com.pixelos.messenger.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Campaign
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

data class AlertMessage(val id: String, val title: String, val body: String, val priority: String)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AlertsScreen(onBack: () -> Unit) {
    val alerts = remember { com.pixelos.messenger.matrix.MatrixClient.getAlerts() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Alertes système") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } }
            )
        }
    ) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding)) {
            items(alerts) { alert ->
                Card(
                    Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = when (alert.priority) {
                            "haute" -> MaterialTheme.colorScheme.errorContainer
                            "moyenne" -> MaterialTheme.colorScheme.tertiaryContainer
                            else -> MaterialTheme.colorScheme.surfaceVariant
                        }
                    )
                ) {
                    Column(Modifier.padding(16.dp)) {
                        Row {
                            Icon(Icons.Default.Campaign, null, Modifier.padding(end = 8.dp))
                            Text(alert.title, fontWeight = FontWeight.Bold)
                        }
                        Spacer(Modifier.height(4.dp))
                        Text(alert.body, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}
