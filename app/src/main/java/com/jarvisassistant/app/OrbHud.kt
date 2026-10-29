package com.jarvisassistant.app

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
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
            val cy = size.height * 0.51f
            val radius = size.minDimension * 0.205f
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
                    radius = radius * (1.12f + i * 0.16f),
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
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(Color(0xFFFFF5B0), Color(0xFFFFB01F), Color(0xFFFF6500), Color(0xFF6A2100)),
                    center = androidx.compose.ui.geometry.Offset(cx - radius * 0.2f, cy - radius * 0.22f),
                    radius = radius * 1.22f
                ),
                radius = radius * pulse,
                center = androidx.compose.ui.geometry.Offset(cx, cy)
            )
            drawCircle(
                color = Color(0xFFFFF4B0).copy(alpha = 0.9f),
                radius = radius * 0.13f,
                center = androidx.compose.ui.geometry.Offset(cx, cy),
            )
            for (i in 0..19) {
                val a = Math.toRadians((i * 18.0 + orbit).toDouble())
                val r = radius * (1.45 + (i % 4) * 0.12)
                val x = cx + kotlin.math.cos(a).toFloat() * r
                val y = cy + kotlin.math.sin(a).toFloat() * r
                drawCircle(color = orange.copy(alpha = 0.45f + (i % 3) * 0.18f), radius = 2.2f + (i % 3), center = androidx.compose.ui.geometry.Offset(x, y))
            }
        }
        Column(
            modifier = Modifier.fillMaxSize().padding(horizontal = 28.dp, vertical = 28.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Row(Modifier.fillMaxSize().weight(1f), verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text("●  J A R V I S", color = orange, fontSize = 17.sp, fontWeight = FontWeight.Medium)
                    Text("Always here for you", color = orange.copy(alpha = 0.85f), fontSize = 11.sp)
                }
                Text("AI SYSTEM  •  ONLINE", color = Color.LightGray, fontSize = 9.sp)
            }
            Spacer(Modifier.height(10.dp))
            Text(
                when (state) {
                    JarvisState.LISTENING -> "“I'M LISTENING”"
                    JarvisState.THINKING -> "ANALYZING"
                    JarvisState.SPEAKING -> "RESPONDING"
                    else -> "“HEY JARVIS”"
                },
                color = orange, fontSize = 17.sp, letterSpacing = 2.sp, fontWeight = FontWeight.Medium
            )
            Spacer(Modifier.weight(1.05f))
            Text("J A R V I S", color = Color.White, fontSize = 25.sp, letterSpacing = 5.sp, fontWeight = FontWeight.Light)
            Text("Your AI Assistant", color = Color.LightGray, fontSize = 14.sp, letterSpacing = 1.sp)
            Spacer(Modifier.height(22.dp))
            Box(
                modifier = Modifier.size(width = 112.dp, height = 66.dp)
                    .clip(CircleShape)
                    .background(Brush.verticalGradient(listOf(Color(0xFFFFB02E), Color(0xFF9B3C00))))
                    .background(Color(0xFF120900)),
                contentAlignment = Alignment.Center
            ) {
                Text("🎙", modifier = Modifier.padding(10.dp), fontSize = 28.sp, textAlign = TextAlign.Center)
                androidx.compose.foundation.layout.Box(
                    Modifier.fillMaxSize().clip(CircleShape)
                        .background(Color.Transparent)
                        .then(Modifier),
                    contentAlignment = Alignment.Center
                ) {}
            }
            Text(
                when (state) {
                    JarvisState.LISTENING -> "LISTENING NOW"
                    JarvisState.THINKING -> "THINKING..."
                    JarvisState.SPEAKING -> "SPEAKING..."
                    else -> "TAP MIC TO TALK  •  SWIPE RIGHT FOR SETTINGS"
                },
                modifier = Modifier.padding(top = 12.dp),
                color = Color(0xFFB5B5B5), fontSize = 9.sp, letterSpacing = 1.2.sp, textAlign = TextAlign.Center
            )
        }
    }
}
