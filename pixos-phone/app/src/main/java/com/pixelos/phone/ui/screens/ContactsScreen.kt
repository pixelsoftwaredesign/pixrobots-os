package com.pixelos.phone.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat

data class Contact(val id: String, val name: String, val number: String, val isPixelUser: Boolean)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ContactsScreen(onBack: () -> Unit, onCall: (String) -> Unit) {
    val ctx = LocalContext.current
    var contacts by remember { mutableStateOf<List<Contact>>(emptyList()) }
    var search by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED) {
            val cursor = ctx.contentResolver.query(android.provider.ContactsContract.CommonDataKinds.Phone.CONTENT_URI, null, null, null, null)
            cursor?.use {
                val list = mutableListOf<Contact>()
                while (it.moveToNext()) {
                    val name = it.getString(it.getColumnIndex(android.provider.ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)) ?: ""
                    val num = it.getString(it.getColumnIndex(android.provider.ContactsContract.CommonDataKinds.Phone.NUMBER)) ?: ""
                    if (name.isNotBlank() && num.isNotBlank()) list.add(Contact("c${list.size}", name, num, false))
                }
                contacts = list.take(100)
            }
        }
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Contacts") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } }) },
        floatingActionButton = { FloatingActionButton({}) { Icon(Icons.Default.Add, null) } }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            OutlinedTextField(value = search, onValueChange = { search = it }, modifier = Modifier.fillMaxWidth().padding(12.dp), placeholder = { Text("Rechercher") }, singleLine = true, leadingIcon = { Icon(Icons.Default.Search, null) })
            LazyColumn {
                val filtered = contacts.filter { it.name.contains(search, ignoreCase = true) || it.number.contains(search) }
                items(filtered) { contact ->
                    Card(onClick = { onCall(contact.number) }, Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 2.dp), elevation = CardDefaults.cardElevation(0.dp)) {
                        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.Person, null, Modifier.padding(end = 12.dp), tint = MaterialTheme.colorScheme.primary)
                            Column(Modifier.weight(1f)) {
                                Text(contact.name, fontWeight = FontWeight.Medium)
                                Text(contact.number, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            if (contact.isPixelUser) Icon(Icons.Default.Shield, null, tint = MaterialTheme.colorScheme.secondary)
                            IconButton({ onCall(contact.number) }) { Icon(Icons.Default.Call, null, tint = MaterialTheme.colorScheme.primary) }
                        }
                    }
                }
            }
        }
    }
}
