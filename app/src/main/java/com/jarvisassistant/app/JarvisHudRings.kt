package com.jarvisassistant.app

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate

/** Marvel-style rotating HUD rings drawn around the core video. */
@Composable
fun JarvisHudRings(state: JarvisState, modifier: Modifier = Modifier) {
    val speed = when (state) {
        JarvisState.THINKING -> 3.0f
        JarvisState.LISTENING -> 1.8f
        JarvisState.SPEAKING -> 1.4f
        else -> 0.7f
    }
    val color = when (state) {
        JarvisState.ERROR, JarvisState.OFFLINE -> Color(0xFFFF4D4D)
        JarvisState.SERIOUS, JarvisState.CYBERSECURITY -> Color(0xFFFFB020)
        else -> Color(0xFF29D9FF)
    }

    val speedNow by rememberUpdatedState(speed)
    var angle by remember { mutableFloatStateOf(0f) }
    LaunchedEffect(Unit) {
        var last = withFrameNanos { it }
        while (true) {
            val now = withFrameNanos { it }
            angle = (angle + (now - last) / 1_000_000_000f * 30f * speedNow) % 360f
            last = now
        }
    }

    val pulse by rememberInfiniteTransition(label = "hudPulse").animateFloat(
        initialValue = 0.55f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(900, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "pulse"
    )
    val glow = if (state == JarvisState.LISTENING || state == JarvisState.SPEAKING) pulse else 0.7f

    Canvas(modifier = modifier) {
        val c = center
        val r = size.minDimension / 2f
        val w = r * 0.012f + 1.5f

        drawCircle(
            brush = Brush.radialGradient(listOf(color.copy(alpha = 0.22f * glow), Color.Transparent), c, r),
            radius = r, center = c
        )
        drawCircle(color.copy(alpha = 0.30f), radius = r * 0.99f, center = c, style = Stroke(w))

        rotate(angle * 0.25f, c) {
            for (i in 0 until 60) {
                val len = if (i % 5 == 0) 0.07f else 0.035f
                rotate(i * 6f, c) {
                    drawLine(
                        color.copy(alpha = if (i % 5 == 0) 0.9f else 0.45f),
                        Offset(c.x, c.y - r * 0.97f), Offset(c.x, c.y - r * (0.97f - len)),
                        strokeWidth = w
                    )
                }
            }
        }

        val big = r * 0.86f
        rotate(angle, c) {
            for (i in 0 until 3) {
                drawArc(
                    color.copy(alpha = glow), i * 120f, 70f, false,
                    Offset(c.x - big, c.y - big), Size(big * 2, big * 2),
                    style = Stroke(w * 3f, cap = StrokeCap.Round)
                )
            }
        }

        val mid = r * 0.79f
        rotate(-angle * 1.4f, c) {
            for (i in 0 until 8) {
                drawArc(
                    color.copy(alpha = 0.6f), i * 45f, 18f, false,
                    Offset(c.x - mid, c.y - mid), Size(mid * 2, mid * 2),
                    style = Stroke(w * 1.5f, cap = StrokeCap.Round)
                )
            }
        }
    }
}
