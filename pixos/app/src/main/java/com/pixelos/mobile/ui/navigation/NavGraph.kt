package com.pixelos.mobile.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.pixelos.mobile.ui.screens.*

@Composable
fun NavGraph() {
    val nav = rememberNavController()
    NavHost(nav, startDestination = "connect") {
        composable("connect") { ConnectScreen(nav) }
        composable("dashboard") { DashboardScreen(nav) }
        composable("tasks") { TasksScreen(nav) }
        composable("wallet") { WalletScreen(nav) }
        composable("dao") { DaoScreen(nav) }
        composable("settings") { SettingsScreen(nav) }
    }
}
