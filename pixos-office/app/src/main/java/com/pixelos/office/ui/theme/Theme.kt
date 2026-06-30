package com.pixelos.office.ui.theme

import androidx.compose.material3.*; import androidx.compose.runtime.Composable; import androidx.compose.ui.graphics.Color

private val Light = lightColorScheme(
    primary = Color(0xFF1B5E20), onPrimary = Color.White, primaryContainer = Color(0xFFC8E6C9),
    secondary = Color(0xFF2E7D32), background = Color(0xFFF5F5F5), surface = Color.White,
    errorContainer = Color(0xFFFFDAD6))

@Composable
fun PixOSOfficeTheme(content: @Composable () -> Unit) { MaterialTheme(colorScheme = Light, content = content) }
