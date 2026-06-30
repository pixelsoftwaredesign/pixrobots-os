package com.pixelos.messenger.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

data class Space(val id: String, val name: String, val members: Int, val isPublic: Boolean)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SpacesScreen(onBack: () -> Unit) {
    val spaces = remember { com.pixelos.messenger.matrix.MatrixClient.getSpaces() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Espaces") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } }
            )
        }
    ) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding)) {
            items(spaces) { space ->
                Card(
                    Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                ) {
                    Row(Modifier.padding(16.dp)) {
                        Column(Modifier.weight(1f)) {
                            Text(space.name, fontWeight = FontWeight.Bold)
                            Text("${space.members} membres · ${if (space.isPublic) "Public" else "Privé"}", style = MaterialTheme.typography.bodySmall)
                        }
                        if (!space.isPublic) Icon(Icons.Default.Lock, "Privé")
                    }
                }
            }
        }
    }
}
