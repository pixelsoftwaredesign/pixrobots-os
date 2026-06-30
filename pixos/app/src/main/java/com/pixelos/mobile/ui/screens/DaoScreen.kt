package com.pixelos.mobile.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import com.pixelos.sdk.network.RetrofitClient
import com.pixelos.sdk.models.Proposal
import kotlinx.coroutines.launch

@Composable
fun DaoScreen(nav: NavController) {
    var proposals by remember { mutableStateOf<List<Proposal>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        scope.launch {
            try {
                val r = RetrofitClient.api.getProposals()
                if (r.isSuccessful) proposals = r.body() ?: emptyList()
            } catch (_: Exception) {}
            loading = false
        }
    }

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Text("DAO - Propositions", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(12.dp))
        if (loading) CircularProgressIndicator()
        else proposals.forEach { p ->
            Card(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                Column(Modifier.padding(12.dp)) {
                    Text(p.title, style = MaterialTheme.typography.titleSmall)
                    Text("Pour: ${p.votesFor} · Contre: ${p.votesAgainst}", style = MaterialTheme.typography.bodySmall)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button({}) { Text("Pour") }
                        OutlinedButton({}) { Text("Contre") }
                    }
                }
            }
        }
    }
}
