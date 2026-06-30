package com.pixelos.phone.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pixelos.phone.telephony.CallManager
import androidx.compose.ui.platform.LocalContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CallScreen(number: String, onBack: () -> Unit) {
    val ctx = LocalContext.current
    var isVoip by remember { mutableStateOf(CallManager.isVoipAvailable(number)) }
    var isMuted by remember { mutableStateOf(false) }
    var onSpeaker by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(if (isVoip) "Appel Pixel" else "Appel GSM") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
            )
        }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding), horizontalAlignment = Alignment.CenterHorizontally) {
            Spacer(Modifier.weight(1f))
            Text(number, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Light)
            Spacer(Modifier.height(8.dp))
            Text(if (isVoip) "Chiffré de bout en bout" else "Appel sortant", color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (isVoip) Icon(Icons.Default.Lock, null, Modifier.padding(top = 4.dp), tint = MaterialTheme.colorScheme.tertiary)

            Spacer(Modifier.weight(1f))
            Row(Modifier.fillMaxWidth().padding(horizontal = 32.dp), horizontalArrangement = Arrangement.SpaceEvenly) {
                IconButton({ isMuted = !isMuted }, Modifier.size(64.dp)) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(if (isMuted) Icons.Default.MicOff else Icons.Default.Mic, null, Modifier.size(28.dp))
                        Text("Micro", style = MaterialTheme.typography.labelSmall)
                    }
                }
                IconButton({ onSpeaker = !onSpeaker }, Modifier.size(64.dp)) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(if (onSpeaker) Icons.Default.VolumeUp else Icons.Default.VolumeDown, null, Modifier.size(28.dp))
                        Text("Haut-p.", style = MaterialTheme.typography.labelSmall)
                    }
                }
                IconButton({ /* basculer VoIP/GSM */ }, Modifier.size(64.dp)) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(if (isVoip) Icons.Default.Wifi else Icons.Default.SignalCellularAlt, null, Modifier.size(28.dp))
                        Text(if (isVoip) "VoIP" else "GSM", style = MaterialTheme.typography.labelSmall)
                    }
                }
            }

            Spacer(Modifier.height(32.dp))
            Button(
                onClick = { onBack() },
                modifier = Modifier.size(80.dp),
                shape = MaterialTheme.shapes.extraLarge,
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
            ) { Icon(Icons.Default.CallEnd, "Raccrocher", modifier = Modifier.size(36.dp)) }
            Spacer(Modifier.height(32.dp))
        }
    }
}
