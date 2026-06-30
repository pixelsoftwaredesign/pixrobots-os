package com.pixelos.office.ui.screens

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

data class TableRecord(val id: Int, val fields: Map<String, String>)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BaseScreen(onBack: () -> Unit) {
    var records = remember {
        mutableStateOf(listOf(
            TableRecord(1, mapOf("Variété" to "Tomate Cœur de Bœuf", "Parcelle" to "A3", "Plantation" to "15/03/2026", "Statut" to "En croissance")),
            TableRecord(2, mapOf("Variété" to "Salade Batavia", "Parcelle" to "B1", "Plantation" to "01/04/2026", "Statut" to "Récolté")),
            TableRecord(3, mapOf("Variété" to "Courgette", "Parcelle" to "A2", "Plantation" to "10/04/2026", "Statut" to "Floraison"))
        ))
    }
    val columns = listOf("Variété", "Parcelle", "Plantation", "Statut")

    Scaffold(
        topBar = { TopAppBar(title = { Text("PixBase") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } }) },
        floatingActionButton = { FloatingActionButton({ /* ajouter */ }) { Icon(Icons.Default.Add, null) } }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Inventaire cultures", fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                IconButton({}) { Icon(Icons.Default.Search, "Rechercher") }
                IconButton({}) { Icon(Icons.Default.FilterList, "Filtrer") }
            }
            HorizontalDivider()

            Row(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surfaceVariant).padding(horizontal = 12.dp, vertical = 8.dp)) {
                columns.forEach { Text(it, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.labelMedium, modifier = Modifier.weight(1f)) }
            }

            LazyColumn {
                items(records.value) { rec ->
                    Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp)) {
                        columns.forEach { col ->
                            Text(rec.fields[col] ?: "", style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
                        }
                    }
                    HorizontalDivider()
                }
            }

            Spacer(Modifier.weight(1f))
            Row(Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("${records.value.size} enregistrements", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                OutlinedButton({ /* exporter */ }) { Icon(Icons.Default.CloudDownload, null, Modifier.padding(end = 4.dp)); Text("Exporter CSV") }
            }
        }
    }
}
