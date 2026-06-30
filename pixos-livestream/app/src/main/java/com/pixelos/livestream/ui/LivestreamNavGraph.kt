package com.pixelos.livestream.ui

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.pixelos.livestream.ui.screens.*

@Composable
fun LivestreamNavGraph() {
    val nav = rememberNavController()
    NavHost(nav, "browse") {
        composable("browse") { BrowseScreen(onGoLive = { nav.navigate("golive") }, onWatch = { id -> nav.navigate("watch/$id") }) }
        composable("golive") { GoLiveScreen(onBack = { nav.popBackStack() }) }
        composable("watch/{streamId}") { WatchScreen(streamId = it.arguments?.getString("streamId") ?: "", onBack = { nav.popBackStack() }) }
    }
}
