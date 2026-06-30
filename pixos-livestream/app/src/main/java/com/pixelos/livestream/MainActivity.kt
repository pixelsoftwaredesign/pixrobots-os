package com.pixelos.livestream

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.pixelos.livestream.ui.LivestreamNavGraph
import com.pixelos.livestream.ui.theme.PixOSLivestreamTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            PixOSLivestreamTheme {
                Surface(Modifier.fillMaxSize()) { LivestreamNavGraph() }
            }
        }
    }
}
