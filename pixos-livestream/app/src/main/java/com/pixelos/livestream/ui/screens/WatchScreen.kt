package com.pixelos.livestream.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WatchScreen(streamId: String, onBack: () -> Unit) {
    var isMuted by remember { mutableStateOf(false) }
    var showChat by remember { mutableStateOf(true) }
    val message = remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Stream $streamId") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } },
                actions = {
                    IconButton({ isMuted = !isMuted }) { Icon(if (isMuted) Icons.Default.VolumeOff else Icons.Default.VolumeUp, null) }
                }
            )
        }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            Box(Modifier.fillMaxWidth().height(240.dp).weight(1f), contentAlignment = Alignment.Center) {
                Surface(color = MaterialTheme.colorScheme.surfaceVariant, modifier = Modifier.fillMaxSize()) {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(Icons.Default.PlayCircle, null, Modifier.size(64.dp), tint = MaterialTheme.colorScheme.primary)
                            Text("Stream vidéo", style = MaterialTheme.typography.bodyLarge)
                            Text("(SurfaceView WebRTC)", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                Surface(color = MaterialTheme.colorScheme.error, shape = MaterialTheme.shapes.extraSmall, modifier = Modifier.align(Alignment.TopStart).padding(8.dp)) {
                    Text("LIVE", color = MaterialTheme.colorScheme.onError, modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp), style = MaterialTheme.typography.labelSmall)
                }
            }

            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Serre Nord — matin", fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                IconButton({}) { Icon(Icons.Default.FavoriteBorder, null) }
                IconButton({}) { Icon(Icons.Default.CardGiftcard, null) }
            }
            Text("Ferme Pixel · 3 spectateurs", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(horizontal = 16.dp))

            HorizontalDivider(Modifier.padding(vertical = 8.dp))

            Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(value = message.value, onValueChange = { message.value = it }, modifier = Modifier.weight(1f), placeholder = { Text("Message...") }, singleLine = true)
                Spacer(Modifier.width(8.dp))
                IconButton({ /* envoyer */ }) { Icon(Icons.Default.Send, "Envoyer") }
            }
        }
    }
}
