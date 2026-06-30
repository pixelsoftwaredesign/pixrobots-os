package com.pixelos.phone

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.pixelos.phone.ui.PhoneNavGraph
import com.pixelos.phone.ui.theme.PixOSPhoneTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { PixOSPhoneTheme { Surface(Modifier.fillMaxSize()) { PhoneNavGraph() } } }
    }
}
