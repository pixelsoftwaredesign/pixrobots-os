package com.pixelos.office

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.pixelos.office.ui.OfficeNavGraph
import com.pixelos.office.ui.theme.PixOSOfficeTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { PixOSOfficeTheme { Surface(Modifier.fillMaxSize()) { OfficeNavGraph() } } }
    }
}
