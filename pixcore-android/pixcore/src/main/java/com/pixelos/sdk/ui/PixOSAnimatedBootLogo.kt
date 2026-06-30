package com.pixelos.sdk.ui

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlin.math.sin

@Composable
fun PixOSAnimatedBootLogo(
    onFinished: () -> Unit,
    durationMs: Long = 3000L
) {
    val infinite = rememberInfiniteTransition(label = "boot")
    val progress by infinite.animateFloat(
        initialValue = 0f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(2000), RepeatMode.Restart),
        label = "progress"
    )

    LaunchedEffect(Unit) { delay(durationMs); onFinished() }

    Box(
        modifier = Modifier.fillMaxSize().background(Color(0xFF0D47A1)),
        contentAlignment = Alignment.Center
    ) {
        Canvas(Modifier.fillMaxSize()) {
            val w = size.width; val h = size.height
            val count = 24

            // Barres lumineuses défilantes (style Android boot)
            for (i in 0 until count) {
                val x = i * (w / count)
                val alpha = (sin(progress * Math.PI * 2 + i * 0.5) * 0.5 + 0.5).toFloat() * 0.8f
                drawRect(Color.White.copy(alpha = alpha), Offset(x, 0f), (w / count) - 1, h)
            }
        }

        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Spacer(Modifier.height(80.dp))
            Text("PIXEL OS", color = Color.White, fontSize = 36.sp, fontWeight = FontWeight.Bold, letterSpacing = 8.sp)
            Spacer(Modifier.height(12.dp))
            Text("Décentralisé · Souverain · Open Source", color = Color.White.copy(alpha = 0.6f), fontSize = 12.sp, letterSpacing = 1.sp)
            Spacer(Modifier.weight(1f))
            Text("Propulsé par pixcore-android", color = Color.White.copy(alpha = 0.4f), fontSize = 10.sp, modifier = Modifier.padding(bottom = 48.dp))
        }
    }
}
