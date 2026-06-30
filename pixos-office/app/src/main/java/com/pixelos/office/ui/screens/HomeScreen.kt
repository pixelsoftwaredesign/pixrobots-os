package com.pixelos.office.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

data class OfficeModule(val route: String, val name: String, val icon: androidx.compose.ui.graphics.vector.ImageVector, val desc: String)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(onOpen: (String) -> Unit) {
    val modules = listOf(
        OfficeModule("docs", "PixDocs", Icons.Default.Description, "Traitement de texte"),
        OfficeModule("sheets", "PixSheets", Icons.Default.TableChart, "Tableur"),
        OfficeModule("slides", "PixSlides", Icons.Default.Slideshow, "Présentations"),
        OfficeModule("base", "PixBase", Icons.Default.Storage, "Base de données")
    )

    Scaffold(topBar = { TopAppBar(title = { Text("PixOS Office") }) }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
            Text("Bienvenue", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Text("Documents, feuilles, présentations et bases de données — décentralisés.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(24.dp))
            modules.forEach { mod ->
                Card(onClick = { onOpen(mod.route) }, modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp), elevation = CardDefaults.cardElevation(2.dp)) {
                    Row(Modifier.padding(20.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                        Icon(mod.icon, null, Modifier.padding(end = 16.dp), tint = MaterialTheme.colorScheme.primary)
                        Column(Modifier.weight(1f)) {
                            Text(mod.name, fontWeight = FontWeight.SemiBold)
                            Text(mod.desc, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Icon(Icons.Default.ChevronRight, null)
                    }
                }
            }
        }
    }
}
