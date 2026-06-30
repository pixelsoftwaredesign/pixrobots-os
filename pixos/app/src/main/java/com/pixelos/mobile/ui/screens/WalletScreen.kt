package com.pixelos.mobile.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import com.pixelos.sdk.wallet.WalletManager
import kotlinx.coroutines.launch

@Composable
fun WalletScreen(nav: NavController) {
    var balance by remember { mutableStateOf("0") }
    var address by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        scope.launch {
            address = WalletManager.address.ifEmpty { "Non connecté" }
            balance = if (WalletManager.isReady()) {
                WalletManager.getBalance().toPlainString()
            } else "0"
        }
    }

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Text("Portefeuille BITROOT", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(24.dp))
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(24.dp)) {
                Text("Solde", style = MaterialTheme.typography.titleMedium)
                Text("$balance BRT", style = MaterialTheme.typography.headlineLarge)
                Spacer(Modifier.height(8.dp))
                Text(address, style = MaterialTheme.typography.bodySmall)
            }
        }
        Spacer(Modifier.height(16.dp))
        OutlinedTextField("", {}, label = { Text("Importer une clé privée") }, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(8.dp))
        Button({}, Modifier.fillMaxWidth()) { Text("Importer") }
    }
}
