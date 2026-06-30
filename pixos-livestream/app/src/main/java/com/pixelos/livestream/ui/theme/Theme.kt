package com.pixelos.livestream.ui.theme

import androidx.compose.material3.*; import androidx.compose.runtime.Composable; import androidx.compose.ui.graphics.Color

private val Light = lightColorScheme(
    primary = Color(0xFFE65100), onPrimary = Color.White, primaryContainer = Color(0xFFFFDBC1),
    secondary = Color(0xFFBF360C), background = Color(0xFFF5F5F5), surface = Color.White,
    errorContainer = Color(0xFFFFDAD6))

@Composable
fun PixOSLivestreamTheme(content: @Composable () -> Unit) { MaterialTheme(colorScheme = Light, content = content) }
