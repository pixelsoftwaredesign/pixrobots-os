package com.pixelos.mobile.ui.theme

import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Color(0xFF2E7D32),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFA5D6A7),
    secondary = Color(0xFF1B5E20),
    tertiary = Color(0xFF66BB6A),
    surface = Color(0xFFF5F5F5),
    background = Color.White,
    error = Color(0xFFD32F2F)
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF66BB6A),
    onPrimary = Color(0xFF003300),
    primaryContainer = Color(0xFF1B5E20),
    secondary = Color(0xFFA5D6A7),
    surface = Color(0xFF1B1B1B),
    background = Color(0xFF121212),
    error = Color(0xFFEF5350)
)

@Composable
fun PixOSTheme(darkTheme: Boolean = false, content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content
    )
}
