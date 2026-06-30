package com.pixelos.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import com.pixelos.mobile.ui.navigation.NavGraph
import com.pixelos.mobile.ui.theme.PixOSTheme
import com.pixelos.sdk.ui.PixOSSplashScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            var showSplash by remember { mutableStateOf(true) }
            PixOSTheme {
                if (showSplash) {
                    PixOSSplashScreen(appName = "PixOS", onSplashFinished = { showSplash = false })
                } else {
                    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                        NavGraph()
                    }
                }
            }
        }
    }
}
