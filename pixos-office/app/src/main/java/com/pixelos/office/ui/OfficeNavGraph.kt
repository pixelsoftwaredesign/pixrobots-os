package com.pixelos.office.ui

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.pixelos.office.ui.screens.*

@Composable
fun OfficeNavGraph() {
    val nav = rememberNavController()
    NavHost(nav, "home") {
        composable("home") { HomeScreen(onOpen = { module -> nav.navigate(module) }) }
        composable("docs") { DocsScreen(onBack = { nav.popBackStack() }) }
        composable("sheets") { SheetsScreen(onBack = { nav.popBackStack() }) }
        composable("slides") { SlidesScreen(onBack = { nav.popBackStack() }) }
        composable("base") { BaseScreen(onBack = { nav.popBackStack() }) }
    }
}
