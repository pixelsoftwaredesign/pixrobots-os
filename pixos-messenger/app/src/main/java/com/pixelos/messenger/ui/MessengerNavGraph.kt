package com.pixelos.messenger.ui

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.pixelos.messenger.ui.screens.AlertsScreen
import com.pixelos.messenger.ui.screens.ChatDetailScreen
import com.pixelos.messenger.ui.screens.ChatsScreen
import com.pixelos.messenger.ui.screens.SettingsScreen
import com.pixelos.messenger.ui.screens.SpacesScreen

@Composable
fun MessengerNavGraph() {
    val navController = rememberNavController()

    NavHost(navController = navController, startDestination = "chats") {
        composable("chats") { ChatsScreen(onChatClick = { roomId -> navController.navigate("chat/$roomId") }, onNavigateToSpaces = { navController.navigate("spaces") }, onNavigateToAlerts = { navController.navigate("alerts") }, onNavigateToSettings = { navController.navigate("settings") }) }
        composable("chat/{roomId}") { ChatDetailScreen(roomId = it.arguments?.getString("roomId") ?: "", onBack = { navController.popBackStack() }) }
        composable("spaces") { SpacesScreen(onBack = { navController.popBackStack() }) }
        composable("alerts") { AlertsScreen(onBack = { navController.popBackStack() }) }
        composable("settings") { SettingsScreen(onBack = { navController.popBackStack() }) }
    }
}
