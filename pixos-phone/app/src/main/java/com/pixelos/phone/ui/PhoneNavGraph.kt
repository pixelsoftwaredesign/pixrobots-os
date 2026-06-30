package com.pixelos.phone.ui

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.pixelos.phone.ui.screens.*

@Composable
fun PhoneNavGraph() {
    val nav = rememberNavController()
    NavHost(nav, "dialer") {
        composable("dialer") { DialerScreen(onCall = { number -> nav.navigate("call/$number") }) }
        composable("contacts") { ContactsScreen(onBack = { nav.popBackStack() }, onCall = { number -> nav.navigate("call/$number") }) }
        composable("recents") { RecentsScreen(onBack = { nav.popBackStack() }, onCall = { number -> nav.navigate("call/$number") }) }
        composable("call/{number}") { CallScreen(number = it.arguments?.getString("number") ?: "", onBack = { nav.popBackStack() }) }
    }
}
