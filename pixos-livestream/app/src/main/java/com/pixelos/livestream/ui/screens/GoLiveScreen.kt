package com.pixelos.livestream.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GoLiveScreen(onBack: () -> Unit) {
    val ctx = LocalContext.current
    var title by remember { mutableStateOf("") }
    var isPrivate by remember { mutableStateOf(false) }
    var streamStarted by remember { mutableStateOf(false) }

    val permLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {}
    val hasPerms = ContextCompat.checkSelfPermission(ctx, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED &&
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED

    LaunchedEffect(Unit) {
        if (!hasPerms) permLauncher.launch(arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO))
    }

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("Go Live") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "Retour") } })
        }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            if (streamStarted) {
                Icon(Icons.Default.Videocam, null, Modifier.size(80.dp), tint = MaterialTheme.colorScheme.error)
                Spacer(Modifier.height(16.dp))
                Text("En direct !", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.headlineSmall)
                Text("Votre stream est diffusé", color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(24.dp))
                OutlinedButton({ streamStarted = false; onBack() }) { Icon(Icons.Default.Stop, null, Modifier.padding(end = 4.dp)); Text("Arrêter le stream") }
            } else {
                Icon(Icons.Default.LiveTv, null, Modifier.size(64.dp), tint = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.height(16.dp))
                OutlinedTextField(value = title, onValueChange = { title = it }, label = { Text("Titre du stream") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                Spacer(Modifier.height(12.dp))
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text("Stream privé", modifier = Modifier.weight(1f))
                    Switch(checked = isPrivate, onCheckedChange = { isPrivate = it })
                }
                Spacer(Modifier.height(8.dp))
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.PhotoCamera, null, Modifier.padding(end = 8.dp))
                    Text("Caméra avant")
                    Spacer(Modifier.weight(1f))
                    Switch(checked = true, onCheckedChange = {})
                }
                Spacer(Modifier.height(24.dp))
                Button(onClick = { streamStarted = true }, modifier = Modifier.fillMaxWidth().height(48.dp), enabled = title.isNotBlank()) {
                    Icon(Icons.Default.FiberManualRecord, null, Modifier.padding(end = 8.dp))
                    Text("Démarrer le stream")
                }
            }
        }
    }
}
