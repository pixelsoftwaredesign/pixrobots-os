package com.pixelos.phone.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pixelos.phone.telephony.CallManager
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RecentsScreen(onBack: () -> Unit, onCall: (String) -> Unit) {
    val ctx = LocalContext.current
    val logs = remember { CallManager.getCallLog(ctx) }
    val dateFormat = remember { SimpleDateFormat("dd/MM HH:mm", Locale.getDefault()) }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Récents") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } }) }
    ) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding)) {
            items(logs) { log ->
                Card(onClick = { onCall(log.number) }, Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 2.dp), elevation = CardDefaults.cardElevation(0.dp)) {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            when (log.type) {
                                android.provider.CallLog.Calls.INCOMING_TYPE -> Icons.Default.PhoneCallback
                                android.provider.CallLog.Calls.OUTGOING_TYPE -> Icons.Default.PhoneForwarded
                                else -> Icons.Default.PhoneMissed
                            }, null, Modifier.padding(end = 12.dp),
                            tint = when (log.type) {
                                android.provider.CallLog.Calls.MISSED_TYPE -> MaterialTheme.colorScheme.error
                                else -> MaterialTheme.colorScheme.primary
                            }
                        )
                        Column(Modifier.weight(1f)) {
                            Text(log.name, fontWeight = FontWeight.Medium)
                            Text(log.number, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Column(horizontalAlignment = Alignment.End) {
                            Text(dateFormat.format(Date(log.date)), style = MaterialTheme.typography.bodySmall)
                            Text("${log.duration / 60}:%02d".format(log.duration % 60), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
    }
}
