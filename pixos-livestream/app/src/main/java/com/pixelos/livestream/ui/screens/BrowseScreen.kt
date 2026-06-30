package com.pixelos.livestream.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

data class StreamInfo(val id: String, val title: String, val streamer: String, val viewers: Int, val live: Boolean)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BrowseScreen(onGoLive: () -> Unit, onWatch: (String) -> Unit) {
    val streams = remember {
        listOf(
            StreamInfo("s1", "Serre Nord — matin", "Ferme Pixel", 3, true),
            StreamInfo("s2", "Inspection robot #2", "TechAgri", 1, true),
            StreamInfo("s3", "Atelier taille", "Coopérative", 8, true),
            StreamInfo("s4", "Marché BITROOT", "PixelDAO", 12, true)
        )
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("PixOS Livestream") }) },
        floatingActionButton = {
            FloatingActionButton(onClick = onGoLive) { Icon(Icons.Default.Videocam, "Go Live") }
        }
    ) { padding ->
        LazyVerticalGrid(
            columns = GridCells.Fixed(2),
            modifier = Modifier.fillMaxSize().padding(padding).padding(8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(streams) { stream ->
                Card(
                    onClick = { onWatch(stream.id) },
                    modifier = Modifier.height(180.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
                ) {
                    Box(Modifier.fillMaxSize().padding(12.dp)) {
                        Column {
                            Icon(Icons.Default.PlayCircle, null, modifier = Modifier.size(32.dp), tint = MaterialTheme.colorScheme.primary)
                            Spacer(Modifier.weight(1f))
                            Text(stream.title, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium)
                            Text(stream.streamer, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Surface(color = MaterialTheme.colorScheme.error, shape = MaterialTheme.shapes.extraSmall) {
                                    Text("LIVE", color = MaterialTheme.colorScheme.onError, style = MaterialTheme.typography.labelSmall, modifier = Modifier.padding(horizontal = 4.dp))
                                }
                                Spacer(Modifier.width(8.dp))
                                Text("${stream.viewers}", style = MaterialTheme.typography.labelSmall)
                                Icon(Icons.Default.Visibility, null, Modifier.size(14.dp).padding(start = 2.dp))
                            }
                        }
                    }
                }
            }
        }
    }
}
