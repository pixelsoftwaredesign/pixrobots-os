package com.pixelos.messenger.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import com.pixelos.messenger.matrix.MatrixClient

data class Message(val id: String, val sender: String, val body: String, val isMine: Boolean)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatDetailScreen(roomId: String, onBack: () -> Unit) {
    var input by remember { mutableStateOf("") }
    val messages = remember { MatrixClient.getMessages(roomId) }
    val roomName = remember { MatrixClient.getRoomName(roomId) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(roomName) },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } }
            )
        }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            LazyColumn(Modifier.weight(1f).padding(horizontal = 12.dp)) {
                items(messages) { msg ->
                    MessageBubble(msg)
                }
            }
            Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = input,
                    onValueChange = { input = it },
                    modifier = Modifier.weight(1f),
                    placeholder = { Text("Message") },
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                    keyboardActions = KeyboardActions(onSend = {
                        if (input.isNotBlank()) {
                            MatrixClient.sendMessage(roomId, input)
                            input = ""
                        }
                    })
                )
                Spacer(Modifier.width(8.dp))
                IconButton({
                    if (input.isNotBlank()) {
                        MatrixClient.sendMessage(roomId, input)
                        input = ""
                    }
                }) { Icon(Icons.Default.Send, "Envoyer") }
            }
        }
    }
}

@Composable
fun MessageBubble(msg: Message) {
    val alignment = if (msg.isMine) Alignment.End else Alignment.Start
    val color = if (msg.isMine) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant

    Column(Modifier.fillMaxWidth().padding(vertical = 2.dp), horizontalAlignment = alignment) {
        Surface(shape = MaterialTheme.shapes.medium, color = color) {
            Column(Modifier.padding(12.dp)) {
                if (!msg.isMine) Text(msg.sender, style = MaterialTheme.typography.labelSmall)
                Text(msg.body)
            }
        }
    }
}
