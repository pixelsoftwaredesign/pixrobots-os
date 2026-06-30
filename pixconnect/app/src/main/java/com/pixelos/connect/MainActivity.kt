package com.pixelos.connect

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.pixelos.connect.ui.ConnectNavGraph
import com.pixelos.connect.ui.theme.PixConnectTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            PixConnectTheme {
                Surface(Modifier.fillMaxSize()) {
                    ConnectNavGraph()
                }
            }
        }
    }
}
