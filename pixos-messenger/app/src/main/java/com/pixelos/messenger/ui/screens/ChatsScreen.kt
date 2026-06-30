package com.pixelos.messenger.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Campaign
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pixelos.messenger.matrix.MatrixClient

data class ChatPreview(val roomId: String, val name: String, val lastMessage: String, val unread: Int)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatsScreen(
    onChatClick: (String) -> Unit,
    onNavigateToSpaces: () -> Unit,
    onNavigateToAlerts: () -> Unit,
    onNavigateToSettings: () -> Unit
) {
    val chats = remember { MatrixClient.getChatPreviews() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("PixOS Messenger") },
                actions = {
                    IconButton(onClick = onNavigateToSpaces) { Icon(Icons.Default.Groups, "Espaces") }
                    IconButton(onClick = onNavigateToAlerts) { Icon(Icons.Default.Campaign, "Alertes") }
                    IconButton(onClick = onNavigateToSettings) { Icon(Icons.Default.Settings, "Paramètres") }
                }
            )
        },
        floatingActionButton = {
            FloatingActionButton({ MatrixClient.createRoom("Nouvelle discussion") }) {
                Icon(Icons.Default.Add, "Nouvelle discussion")
            }
        }
    ) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding)) {
            items(chats) { chat ->
                ChatItem(chat, onClick = { onChatClick(chat.roomId) })
            }
        }
    }
}

@Composable
fun ChatItem(chat: ChatPreview, onClick: () -> Unit) {
    Card(
        Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp).clickable(onClick = onClick),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(chat.name, fontWeight = FontWeight.Bold)
                Text(chat.lastMessage, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (chat.unread > 0) {
                Badge { Text("${chat.unread}") }
            }
        }
    }
}
