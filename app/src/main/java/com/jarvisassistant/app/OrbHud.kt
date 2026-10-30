package com.jarvisassistant.app

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun OrbHud(state: JarvisState, onMicTap: () -> Unit, modifier: Modifier = Modifier) {
    val transition = rememberInfiniteTransition(label = "jarvis_orb")
    val pulse by transition.animateFloat(
        initialValue = 0.94f, targetValue = 1.06f,
        animationSpec = infiniteRepeatable(tween(1700, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "orb_pulse"
    )
    val orbit by transition.animateFloat(
        initialValue = 0f, targetValue = 360f,
        animationSpec = infiniteRepeatable(tween(12000, easing = androidx.compose.animation.core.LinearEasing)),
        label = "orb_orbit"
    )
    val active = state == JarvisState.LISTENING || state == JarvisState.THINKING || state == JarvisState.SPEAKING
    val orange = Color(0xFFFF8A00)
    val status = when (state) {
        JarvisState.LISTENING -> "LISTENING"
        JarvisState.THINKING -> "PROCESSING"
        JarvisState.SPEAKING -> "SPEAKING"
        JarvisState.ERROR -> "SYSTEM ALERT"
        JarvisState.OFFLINE -> "OFFLINE MODE"
        else -> "LISTENING FOR"
    }
    Box(modifier = modifier.fillMaxSize().background(Color.Black)) {
        Canvas(Modifier.fillMaxSize()) {
            val cx = size.width * 0.5f
            val cy = size.height * 0.526f
            val radius = size.minDimension * 0.218f
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color(0x66FF6A00), Color(0x22FF6A00), Color.Transparent),
                    center = androidx.compose.ui.geometry.Offset(cx, cy),
                    radius = radius * 2.2f
                ),
                radius = radius * 2.2f,
                center = androidx.compose.ui.geometry.Offset(cx, cy)
            )
            for (i in 1..5) {
                drawCircle(
                    color = orange.copy(alpha = if (i % 2 == 0) 0.25f else 0.48f),
                    radius = radius * (1.12f + (i - 1) * 0.17f),
                    center = androidx.compose.ui.geometry.Offset(cx, cy),
                    style = Stroke(width = if (i == 1) 2.2f else 1f)
                )
            }
            drawArc(
                color = orange,
                startAngle = orbit,
                sweepAngle = 88f,
                useCenter = false,
                topLeft = androidx.compose.ui.geometry.Offset(cx - radius * 1.48f, cy - radius * 1.48f),
                size = androidx.compose.ui.geometry.Size(radius * 2.96f, radius * 2.96f),
                style = Stroke(width = 3.5f)
            )
            drawArc(
                color = Color(0xFFFFB347).copy(alpha = 0.8f),
                startAngle = orbit * -1.2f,
                sweepAngle = 42f,
                useCenter = false,
                topLeft = androidx.compose.ui.geometry.Offset(cx - radius * 1.72f, cy - radius * 1.72f),
                size = androidx.compose.ui.geometry.Size(radius * 3.44f, radius * 3.44f),
                style = Stroke(width = 2f)
            )
            // Fiery plasma sphere: glowing orange perimeter, deep translucent interior,
            // dense sparks, and layered sweeping energy ribbons (matching supplied reference).
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        Color(0xFF170400),
                        Color(0xFF3A0900),
                        Color(0xFF9B1D00),
                        Color(0xFFFF4B00),
                        Color(0xFFFFA020),
                        Color(0xFFFF5A00)
                    ),
                    center = androidx.compose.ui.geometry.Offset(cx - radius * 0.08f, cy - radius * 0.10f),
                    radius = radius * 1.12f
                ),
                radius = radius * pulse,
                center = androidx.compose.ui.geometry.Offset(cx, cy)
            )
            // Fine plasma grain spread over the whole sphere.
            for (i in 0 until 1900) {
                val angle = i * 2.3999632 + orbit * 0.003f
                val spread = kotlin.math.sqrt(((i * 97 % 1901) / 1901.0)).toFloat()
                val px = cx + kotlin.math.cos(angle).toFloat() * radius * 0.985f * spread
                val py = cy + kotlin.math.sin(angle).toFloat() * radius * 0.985f * spread
                val shimmer = 0.16f + ((i * 17 % 79) / 100f)
                drawCircle(
                    color = if (i % 17 == 0) Color(0xFFFFE5A0).copy(alpha = shimmer)
                    else Color(0xFFFF5A08).copy(alpha = shimmer * 0.82f),
                    radius = if (i % 13 == 0) 1.6f else 0.45f + (i % 4) * 0.22f,
                    center = androidx.compose.ui.geometry.Offset(px, py)
                )
            }
            // Interwoven luminous ribbons sweep around the orb at different inclinations.
            for (i in 0..5) {
                val rotation = orbit * (if (i % 2 == 0) 0.42f else -0.31f) + i * 31f
                drawContext.transform.rotate(rotation, pivot = androidx.compose.ui.geometry.Offset(cx, cy))
                drawOval(
                    color = (if (i % 2 == 0) Color(0xFFFFA12A) else Color(0xFFFF4B08)).copy(alpha = 0.72f),
                    topLeft = androidx.compose.ui.geometry.Offset(cx - radius * (0.98f - i * 0.025f), cy - radius * (0.42f + i * 0.035f)),
                    size = androidx.compose.ui.geometry.Size(radius * 1.96f, radius * (0.84f + i * 0.07f)),
                    style = Stroke(width = if (i % 2 == 0) 2.1f else 1.25f)
                )
                drawContext.transform.rotate(-rotation, pivot = androidx.compose.ui.geometry.Offset(cx, cy))
            }
            // Bright, thin outer plasma edge.
            drawCircle(
                color = Color(0xFFFF8A18).copy(alpha = 0.9f),
                radius = radius * 0.995f,
                center = androidx.compose.ui.geometry.Offset(cx, cy),
                style = Stroke(width = 2.2f)
            )
            for (i in 0..19) {
                val a = Math.toRadians((i * 18.0 + orbit).toDouble())
                val r = radius * (1.45f + (i % 4) * 0.12f)
                val x = cx + kotlin.math.cos(a).toFloat() * r
                val y = cy + kotlin.math.sin(a).toFloat() * r
                drawCircle(color = orange.copy(alpha = 0.45f + (i % 3) * 0.18f), radius = 2.2f + (i % 3), center = androidx.compose.ui.geometry.Offset(x, y))
            }
        }
        Column(
            modifier = Modifier.fillMaxSize().padding(horizontal = 32.dp, vertical = 58.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Row(Modifier.fillMaxSize().weight(1f), verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text("●  J A R V I S", color = orange, fontSize = 18.sp, fontWeight = FontWeight.Medium, letterSpacing = 2.sp)
                    Text("Always here for you", color = Color(0xFFD17A28), fontSize = 12.sp)
                }
                Text("AI SYSTEM  •  ONLINE", color = Color(0xFFBDBDBD), fontSize = 9.sp)
            }
            Spacer(Modifier.height(8.dp))
            Text(
                when (state) {
                    JarvisState.LISTENING -> "“I'M LISTENING”"
                    JarvisState.THINKING -> "ANALYZING"
                    JarvisState.SPEAKING -> "RESPONDING"
                    else -> "“HEY JARVIS”"
                },
                color = Color(0xFFFF9A24), fontSize = 17.sp, letterSpacing = 2.sp, fontWeight = FontWeight.Medium
            )
            Spacer(Modifier.weight(1.18f))
            Text("J A R V I S", color = Color(0xFFF0F0F0), fontSize = 25.sp, letterSpacing = 6.sp, fontWeight = FontWeight.Light)
            Text("Your AI Assistant", color = Color(0xFFBDBDBD), fontSize = 14.sp, letterSpacing = 1.sp)
            Spacer(Modifier.height(24.dp))
            Box(
                modifier = Modifier.size(width = 150.dp, height = 88.dp)
                    .clip(CircleShape)
                    .background(Color(0xFF100800))
                    .clickable(onClick = onMicTap),
                contentAlignment = Alignment.Center
            ) {
                Text("🎙", modifier = Modifier.padding(10.dp), fontSize = 31.sp, textAlign = TextAlign.Center)
            }
            Text(
                when (state) {
                    JarvisState.LISTENING -> "LISTENING NOW"
                    JarvisState.THINKING -> "THINKING..."
                    JarvisState.SPEAKING -> "SPEAKING..."
                    else -> "TAP MIC TO TALK"
                },
                modifier = Modifier.padding(top = 14.dp),
                color = Color(0xFFB5B5B5), fontSize = 9.sp, letterSpacing = 1.5.sp, textAlign = TextAlign.Center
            )
        }
    }
}
