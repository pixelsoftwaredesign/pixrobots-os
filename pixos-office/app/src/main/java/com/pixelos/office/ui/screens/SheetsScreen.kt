package com.pixelos.office.ui.screens

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SheetsScreen(onBack: () -> Unit) {
    var cells by remember { mutableStateOf(List(5) { MutableList(4) { "" } }) }

    Scaffold(
        topBar = { TopAppBar(title = { Text("PixSheets") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } }) }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            Row(Modifier.horizontalScroll(rememberScrollState()).padding(start = 48.dp)) {
                listOf("A", "B", "C", "D").forEach { col ->
                    Box(Modifier.width(100.dp).padding(4.dp)) { Text(col, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth()) }
                }
            }
            Column(Modifier.verticalScroll(rememberScrollState()).horizontalScroll(rememberScrollState())) {
                cells.forEachIndexed { rowIdx, row ->
                    Row {
                        Box(Modifier.width(48.dp).padding(4.dp)) { Text("${rowIdx + 1}", fontWeight = FontWeight.Bold, modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Center) }
                        row.forEachIndexed { colIdx, _ ->
                            OutlinedTextField(
                                value = cells[rowIdx][colIdx],
                                onValueChange = { cells[rowIdx][colIdx] = it },
                                modifier = Modifier.width(100.dp).padding(2.dp),
                                singleLine = true,
                                textStyle = MaterialTheme.typography.bodySmall
                            )
                        }
                    }
                }
            }
            Spacer(Modifier.weight(1f))
            Row(Modifier.fillMaxWidth().padding(8.dp), horizontalArrangement = Arrangement.SpaceEvenly) {
                Text("Σ = SOMME(A1:A5)", style = MaterialTheme.typography.bodySmall)
                Text("= MOYENNE(B1:B5)", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
