package com.pixelos.phone.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DialerScreen(onCall: (String) -> Unit) {
    var number by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("PixOS Phone") },
                actions = { IconButton({ onCall("contacts") }) { Icon(Icons.Default.Person, null) }
                           IconButton({ onCall("recents") }) { Icon(Icons.Default.History, null) } })
        }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding), horizontalAlignment = Alignment.CenterHorizontally) {
            Spacer(Modifier.height(24.dp))
            OutlinedTextField(
                value = number,
                onValueChange = { number = it.take(20) },
                modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp),
                placeholder = { Text("Numéro") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                singleLine = true,
                textStyle = MaterialTheme.typography.headlineMedium.copy(fontWeight = FontWeight.Light),
                trailingIcon = { if (number.isNotBlank()) IconButton({ number = "" }) { Icon(Icons.Default.Clear, null) } }
            )
            Spacer(Modifier.height(16.dp))
            Button(
                onClick = { if (number.isNotBlank()) onCall(number) },
                modifier = Modifier.size(72.dp),
                shape = MaterialTheme.shapes.extraLarge,
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
            ) { Icon(Icons.Default.Call, "Appeler", modifier = Modifier.size(32.dp)) }

            Spacer(Modifier.height(24.dp))
            val keys = listOf(
                listOf("1", "2", "3"), listOf("4", "5", "6"),
                listOf("7", "8", "9"), listOf("*", "0", "#")
            )
            keys.forEach { row ->
                Row(Modifier.fillMaxWidth().height(72.dp), horizontalArrangement = Arrangement.SpaceEvenly) {
                    row.forEach { key ->
                        TextButton(
                            onClick = { number += key },
                            modifier = Modifier.size(72.dp),
                            contentPadding = PaddingValues(0.dp)
                        ) { Text(key, fontSize = 28.sp, fontWeight = FontWeight.Normal) }
                    }
                }
            }
        }
    }
}
