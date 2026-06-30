package com.pixelos.mobile.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import com.pixelos.sdk.network.RetrofitClient
import com.pixelos.sdk.models.Task
import kotlinx.coroutines.launch

@Composable
fun TasksScreen(nav: NavController) {
    var tasks by remember { mutableStateOf<List<Task>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        scope.launch {
            try {
                val r = RetrofitClient.api.getTasks()
                if (r.isSuccessful) tasks = r.body() ?: emptyList()
            } catch (_: Exception) {}
            loading = false
        }
    }

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Text("Tâches", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(12.dp))
        if (loading) CircularProgressIndicator()
        else if (tasks.isEmpty()) Text("Aucune tâche")
        else tasks.forEach { task ->
            Card(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                Column(Modifier.padding(12.dp)) {
                    Text(task.title, style = MaterialTheme.typography.titleSmall)
                    Text(task.status, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
                }
            }
        }
    }
}
