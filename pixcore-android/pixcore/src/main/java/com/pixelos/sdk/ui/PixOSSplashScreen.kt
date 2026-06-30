package com.pixelos.sdk.ui

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay

@Composable
fun PixOSSplashScreen(
    appName: String = "Pixel OS",
    onSplashFinished: () -> Unit,
    durationMs: Long = 2000L
) {
    val infiniteTransition = rememberInfiniteTransition(label = "logo")
    val phase by infiniteTransition.animateFloat(
        initialValue = 0f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1200, easing = LinearEasing), RepeatMode.Restart),
        label = "phase"
    )
    val alpha by infiniteTransition.animateFloat(
        initialValue = 0.3f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(800, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "alpha"
    )

    LaunchedEffect(Unit) {
        delay(durationMs)
        onSplashFinished()
    }

    Box(
        modifier = Modifier.fillMaxSize().background(Color(0xFF0D47A1)),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Canvas(Modifier.size(160.dp)) {
                val cx = size.width / 2; val cy = size.height / 2; val r = size.minDimension / 3

                // Anneau extérieur animé
                drawCircle(Color.White.copy(alpha = 0.3f), r + 20, Offset(cx, cy), style = Stroke(3f))
                drawCircle(Color.White.copy(alpha = alpha), r + 20, Offset(cx, cy),
                    style = Stroke(2f), topLeft = Offset(cx - r - 20, cy - r - 20),
                    startAngle = 0f, sweepAngle = 360f * phase, useCenter = false)

                // Hexagone Pixel
                val hex = Path().apply {
                    moveTo(cx, cy - r)
                    for (i in 1..6) {
                        val angle = Math.toRadians((60.0 * i) - 90.0)
                        lineTo((cx + r * Math.cos(angle)).toFloat(), (cy + r * Math.sin(angle)).toFloat())
                    }
                    close()
                }
                drawPath(hex, Color.White, style = Stroke(4f))

                // Points aux sommets
                for (i in 0..5) {
                    val angle = Math.toRadians((60.0 * i) - 90.0)
                    val px = (cx + r * Math.cos(angle)).toFloat()
                    val py = (cy + r * Math.sin(angle)).toFloat()
                    drawCircle(Color.White, 6f, Offset(px, py))
                }

                // Lettre P centrale
                val pSize = r * 0.6f
                val pPath = Path().apply {
                    arcTo(Offset(cx - pSize / 2, cy - pSize / 2), pSize, pSize, 0f, 180f, 180f, false)
                    lineTo(cx - pSize / 2, cy + pSize / 2)
                    close()
                }
                drawPath(pPath, Color.White.copy(alpha = 0.9f))
            }
            Spacer(Modifier.height(24.dp))
            Text("Pixel OS", color = Color.White, fontSize = 28.sp, fontWeight = FontWeight.Bold, letterSpacing = 4.sp)
            Text(appName, color = Color.White.copy(alpha = 0.7f), fontSize = 14.sp, letterSpacing = 2.sp)
        }
    }
}
