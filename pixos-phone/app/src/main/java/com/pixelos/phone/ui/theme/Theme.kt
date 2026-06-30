package com.pixelos.phone.ui.theme

import androidx.compose.material3.*; import androidx.compose.runtime.Composable; import androidx.compose.ui.graphics.Color

private val Light = lightColorScheme(
    primary = Color(0xFF4A148C), onPrimary = Color.White, primaryContainer = Color(0xFFE1BEE7),
    secondary = Color(0xFF6A1B9A), background = Color(0xFFF5F5F5), surface = Color.White,
    errorContainer = Color(0xFFFFDAD6))

@Composable
fun PixOSPhoneTheme(content: @Composable () -> Unit) { MaterialTheme(colorScheme = Light, content = content) }
