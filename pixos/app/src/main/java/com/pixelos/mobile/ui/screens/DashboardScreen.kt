package com.pixelos.mobile.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import com.pixelos.sdk.PixCore
import com.pixelos.sdk.network.RetrofitClient
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(nav: NavController) {
    var statusText by remember { mutableStateOf("Chargement...") }
    val scope = rememberCoroutineScope()
    var selectedTab by remember { mutableIntStateOf(0) }

    LaunchedEffect(Unit) {
        scope.launch {
            try {
                val r = RetrofitClient.api.getServerStatus()
                statusText = if (r.isSuccessful) "✓ ${r.body()?.version ?: "Connecté"}" else "✗ ${r.code()}"
            } catch (_: Exception) { statusText = "✗ Hors ligne" }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("PixOS") }, actions = {
                Text(statusText, style = MaterialTheme.typography.bodySmall)
            })
        },
        bottomBar = {
            BottomNavigationBar(selectedTab) { selectedTab = it }
        }
    ) { padding ->
        when (selectedTab) {
            0 -> OverviewScreen(nav, Modifier.padding(padding))
            1 -> TasksScreen(nav)
            2 -> WalletScreen(nav)
        }
    }
}

@Composable
fun BottomNavigationBar(selected: Int, onSelect: (Int) -> Unit) {
    NavigationBar {
        NavigationBarItem(selected == 0, { onSelect(0) }, icon = { Icon(Icons.Default.Home, null) }, label = { Text("Accueil") })
        NavigationBarItem(selected == 1, { onSelect(1) }, icon = { Icon(Icons.Default.List, null) }, label = { Text("Tâches") })
        NavigationBarItem(selected == 2, { onSelect(2) }, icon = { Icon(Icons.Default.AccountBalanceWallet, null) }, label = { Text("Wallet") })
    }
}

@Composable
fun OverviewScreen(nav: NavController, mod: Modifier) {
    Column(mod.padding(16.dp)) {
        Text("Pixel OS Mobile", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(8.dp))
        Text("Nœud: ${PixCore.context.packageName}", style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(8.dp))
        Text("Mode nœud: ${if (PixCore.nodeMode) "Actif" else "Inactif"}")
        Spacer(Modifier.height(24.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Card(Modifier.weight(1f)) { Column(Modifier.padding(16.dp)) { Text("Capteurs", style = MaterialTheme.typography.titleSmall); Text("En ligne") } }
            Card(Modifier.weight(1f)) { Column(Modifier.padding(16.dp)) { Text("Robots", style = MaterialTheme.typography.titleSmall); Text("Connectés") } }
        }
    }
}

// Using material.icons.Icons.Default
private val Icons = androidx.compose.material.icons.Icons
