package com.pixelos.connect.ui

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.pixelos.connect.ui.screens.*

@Composable
fun ConnectNavGraph() {
    val navController = rememberNavController()

    NavHost(navController = navController, startDestination = "dashboard") {
        composable("dashboard") { DashboardScreen(onNavigate = { route -> navController.navigate(route) }) }
        composable("wifi") { WifiScreen(onBack = { navController.popBackStack() }) }
        composable("bluetooth") { BluetoothScreen(onBack = { navController.popBackStack() }) }
        composable("data") { DataScreen(onBack = { navController.popBackStack() }) }
        composable("mesh") { MeshScreen(onBack = { navController.popBackStack() }) }
        composable("firewall") { FirewallScreen(onBack = { navController.popBackStack() }) }
        composable("profiles") { ProfilesScreen(onBack = { navController.popBackStack() }) }
    }
}
