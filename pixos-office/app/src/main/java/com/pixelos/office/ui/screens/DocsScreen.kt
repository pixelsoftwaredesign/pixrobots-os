package com.pixelos.office.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

data class Document(val id: String, val title: String, val updated: String, val author: String)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DocsScreen(onBack: () -> Unit) {
    val docs = remember {
        listOf(
            Document("d1", "Rapport de récolte Q2", "12 juin 2026", "Jean"),
            Document("d2", "Manuel irrigation goutte-à-goutte", "8 juin 2026", "Marie"),
            Document("d3", "Plan de culture 2026", "1 juin 2026", "Pierre")
        )
    }
    var content by remember { mutableStateOf("") }
    var showEditor by remember { mutableStateOf(false) }

    Scaffold(
        topBar = { TopAppBar(title = { Text("PixDocs") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } }) },
        floatingActionButton = { FloatingActionButton({ showEditor = true }) { Icon(Icons.Default.Add, "Nouveau doc") } }
    ) { padding ->
        if (showEditor) {
            Column(Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
                Text("Nouveau document", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(value = content, onValueChange = { content = it }, modifier = Modifier.weight(1f).fillMaxWidth(), placeholder = { Text("Écrivez ici... (Markdown supporté)") })
                Spacer(Modifier.height(8.dp))
                Button({ showEditor = false; content = "" }) { Icon(Icons.Default.Save, null, Modifier.padding(end = 4.dp)); Text("Enregistrer") }
            }
        } else {
            LazyColumn(Modifier.fillMaxSize().padding(padding)) {
                items(docs) { doc ->
                    Card(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp), elevation = CardDefaults.cardElevation(1.dp)) {
                        Row(Modifier.padding(16.dp)) {
                            Icon(Icons.Default.Description, null, Modifier.padding(end = 12.dp), tint = MaterialTheme.colorScheme.primary)
                            Column(Modifier.weight(1f)) {
                                Text(doc.title, fontWeight = FontWeight.Medium)
                                Text("${doc.author} · ${doc.updated}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            IconButton({}) { Icon(Icons.Default.MoreVert, null) }
                        }
                    }
                }
            }
        }
    }
}
