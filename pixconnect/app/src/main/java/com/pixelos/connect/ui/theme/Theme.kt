package com.pixelos.connect.ui.theme

import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColorScheme = lightColorScheme(
    primary = Color(0xFF004D40),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFB2DFDB),
    secondary = Color(0xFF00695C),
    tertiary = Color(0xFF1B5E20),
    background = Color(0xFFF5F5F5),
    surface = Color.White,
    error = Color(0xFFB71C1C),
    errorContainer = Color(0xFFFFDAD6)
)

@Composable
fun PixConnectTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = LightColorScheme, content = content)
}
