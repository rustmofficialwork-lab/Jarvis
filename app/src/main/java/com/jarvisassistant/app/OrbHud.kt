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
            // Molten orange shell with a dark, hollow-looking core.
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color(0xFFFFB52C), Color(0xFFFF7A00), Color(0xFFFF5100), Color(0xFF9A3100)),
                    center = androidx.compose.ui.geometry.Offset(cx - radius * 0.16f, cy - radius * 0.2f),
                    radius = radius * 1.18f
                ),
                radius = radius * pulse,
                center = androidx.compose.ui.geometry.Offset(cx, cy)
            )
            // Hundreds of deterministic glowing specks create the particle-mesh look.
            for (i in 0 until 560) {
                val angle = i * 2.3999632 + orbit * 0.0045
                val spread = kotlin.math.sqrt(((i * 97 % 563) / 563.0)).toFloat()
                val px = cx + kotlin.math.cos(angle).toFloat() * radius * 0.97f * spread
                val py = cy + kotlin.math.sin(angle).toFloat() * radius * 0.97f * spread
                val shimmer = 0.28f + ((i * 13 % 67) / 100f)
                drawCircle(
                    color = if (i % 11 == 0) Color(0xFFFFE8A0).copy(alpha = shimmer)
                    else Color(0xFFFF6A00).copy(alpha = shimmer),
                    radius = if (i % 9 == 0) 1.8f else 0.75f + (i % 3) * 0.35f,
                    center = androidx.compose.ui.geometry.Offset(px, py)
                )
            }
            // Dark core and sweeping curved energy ribbons, like the selected reference.
            drawCircle(
                color = Color(0xFF321405).copy(alpha = 0.96f),
                radius = radius * 0.64f,
                center = androidx.compose.ui.geometry.Offset(cx + radius * 0.05f, cy + radius * 0.08f)
            )
            drawArc(
                color = Color(0xFFFFB34D).copy(alpha = 0.82f),
                startAngle = 202f + orbit * 0.45f,
                sweepAngle = 215f,
                useCenter = false,
                topLeft = androidx.compose.ui.geometry.Offset(cx - radius * 0.96f, cy - radius * 0.78f),
                size = androidx.compose.ui.geometry.Size(radius * 1.92f, radius * 1.56f),
                style = Stroke(width = 2.4f)
            )
            drawArc(
                color = Color(0xFFFF7A00).copy(alpha = 0.78f),
                startAngle = 25f - orbit * 0.32f,
                sweepAngle = 248f,
                useCenter = false,
                topLeft = androidx.compose.ui.geometry.Offset(cx - radius * 0.88f, cy - radius * 0.52f),
                size = androidx.compose.ui.geometry.Size(radius * 1.76f, radius * 1.04f),
                style = Stroke(width = 1.7f)
            )
            drawCircle(
                color = Color(0xFFFFF4B0).copy(alpha = 0.9f),
                radius = radius * 0.125f,
                center = androidx.compose.ui.geometry.Offset(cx, cy),
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
