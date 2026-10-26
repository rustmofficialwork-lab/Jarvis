package com.jarvisassistant.app

import android.content.SharedPreferences
import android.os.Build
import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.boundsInWindow
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import kotlin.math.roundToInt
import kotlinx.coroutines.delay

private val PanelBg = Color(0xFF0A0A0A)
private val Ink = Color(0xFFF4F4F4)

private val LOCALES = listOf(
    "en-US" to "EN-US",
    "en-IN" to "EN-IN",
    "en-GB" to "EN-GB",
    "hi-IN" to "HI-IN"
)

// CUSTOM WHITE COLOR SCHEME
private val WhiteColorScheme = darkColorScheme(
    primary = Color.White,
    onPrimary = Color.Black,
    secondary = Color.White,
    onSecondary = Color.Black
)

/**
 * Compose library version se independent gesture exclusion.
 * Is area par system back-swipe disable hota hai (Android 10+ / API 29+).
 */
@Composable
private fun Modifier.gestureExclusion(): Modifier {
    val view = LocalView.current
    DisposableEffect(view) {
        onDispose {
            if (Build.VERSION.SDK_INT >= 29) {
                view.systemGestureExclusionRects = emptyList()
            }
        }
    }
    return this.onGloballyPositioned { coords ->
        if (Build.VERSION.SDK_INT >= 29) {
            val b = coords.boundsInWindow()
            view.systemGestureExclusionRects = listOf(
                android.graphics.Rect(
                    b.left.roundToInt(),
                    b.top.roundToInt(),
                    b.right.roundToInt(),
                    b.bottom.roundToInt()
                )
            )
        }
    }
}

/**
 * Right-edge swipe handle.
 * Swipe left (or tap) to open settings.
 *
 * Gesture navigation ke back-swipe se bachne ke liye is handle par
 * gestureExclusion lagaya hai. Android sirf ~200dp height tak
 * exclusion allow karta hai, isliye handle chhota (160dp) rakha hai.
 */
@Composable
fun BoxScope.EdgeSwipeStrip(onOpen: () -> Unit) {

    Box(
        modifier = Modifier
            .align(Alignment.TopEnd)
            .padding(top = 140.dp)          // handle ka top position
            .width(56.dp)
            .height(160.dp)                 // 200dp se kam rakho
            .gestureExclusion()             // system back gesture yahan disable
            .pointerInput(Unit) { detectTapGestures(onTap = { onOpen() }) }
            .pointerInput(Unit) {
                var total = 0f
                detectHorizontalDragGestures(
                    onDragStart = { total = 0f },
                    onHorizontalDrag = { _, dragAmount ->
                        total += dragAmount
                        if (total < -48f) {
                            total = 0f
                            onOpen()
                        }
                    }
                )
            }
    ) {
        // Visible hint line (handle ke andar, right edge par)
        Box(
            modifier = Modifier
                .align(Alignment.CenterEnd)
                .size(width = 14.dp, height = 70.dp)
                .clip(RoundedCornerShape(topStart = 10.dp, bottomStart = 10.dp))
                .background(Color.White.copy(alpha = 0.85f))
        )
    }
}

@Composable
fun BoxScope.SettingsDrawer(
    visible: Boolean,
    apiKey: String,
    endpoint: String,
    model: String,
    wakeWord: String,
    speechLocale: String,
    speechRate: Float,
    testStatus: String,
    prefs: SharedPreferences,
    onSaveText: (String, String, String, String) -> Unit,
    onLocaleChange: (String) -> Unit,
    onRateChange: (Float) -> Unit,
    onTestApi: (String, String, String) -> Unit,
    onClearHistory: () -> Unit,
    onStartBg: () -> Unit,
    onStopBg: () -> Unit,
    onClose: () -> Unit
) {
    var keyInput by remember(apiKey) { mutableStateOf(apiKey) }
    var showKey by remember { mutableStateOf(false) }
    var saved by remember { mutableStateOf(false) }
    
    // Background variables
    var followUp by remember { mutableStateOf(prefs.getBoolean("follow_up", true)) }
    var beep by remember { mutableStateOf(prefs.getBoolean("wake_beep", false)) }
    var wakeLockOn by remember { mutableStateOf(prefs.getBoolean("use_wakelock", true)) }
    var onBoot by remember { mutableStateOf(prefs.getBoolean("wake_on_boot", true)) }
    var btMic by remember { mutableStateOf(prefs.getBoolean("bt_mic", false)) }
    var bgOn by remember { mutableStateOf(JarvisWakeService.isRunning) }

    LaunchedEffect(visible) {
        while (visible) {
            bgOn = JarvisWakeService.isRunning
            delay(1000)
        }
    }

    LaunchedEffect(saved) {
        if (saved) {
            delay(1500)
            saved = false
        }
    }

    val requestClose = {
        onClose()
    }

    val closeNow by rememberUpdatedState(requestClose)

    BackHandler(enabled = visible) {
        closeNow()
    }

    // Dim background
    AnimatedVisibility(
        visible = visible,
        enter = fadeIn(animationSpec = tween(200)),
        exit = fadeOut(animationSpec = tween(200))
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black.copy(alpha = 0.6f))
                .pointerInput(Unit) { detectTapGestures(onTap = { closeNow() }) }
                .pointerInput(Unit) {
                    detectHorizontalDragGestures(
                        onHorizontalDrag = { _, dragAmount -> if (dragAmount > 12f) closeNow() }
                    )
                }
        )
    }

    // Settings drawer
    AnimatedVisibility(
        visible = visible,
        modifier = Modifier.align(Alignment.CenterEnd),
        enter = slideInHorizontally(initialOffsetX = { it }, animationSpec = tween(250)) + fadeIn(animationSpec = tween(250)),
        exit = slideOutHorizontally(targetOffsetX = { it }, animationSpec = tween(200)) + fadeOut(animationSpec = tween(200))
    ) {
        // Using the new White Color Scheme
        MaterialTheme(colorScheme = WhiteColorScheme) {
            Surface(
                modifier = Modifier
                    .fillMaxHeight()
                    .width(330.dp)
                    .pointerInput(Unit) {
                        detectHorizontalDragGestures(
                            onHorizontalDrag = { _, dragAmount -> if (dragAmount > 20f) closeNow() }
                        )
                    },
                color = PanelBg,
                shape = RoundedCornerShape(topStart = 24.dp, bottomStart = 24.dp),
                border = BorderStroke(1.dp, Color.White.copy(alpha = 0.15f))
            ) {
                Column(
                    modifier = Modifier
                        .verticalScroll(rememberScrollState())
                        .padding(horizontal = 20.dp, vertical = 24.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Text(
                        "Settings",
                        color = Ink,
                        fontWeight = FontWeight.Bold,
                        style = MaterialTheme.typography.titleLarge
                    )

                    Text(
                        "Swipe from the right edge anytime to open this.",
                        color = Ink.copy(alpha = 0.55f),
                        style = MaterialTheme.typography.bodySmall
                    )

                    SectionTitle("Assistant")

                    // Sirf API Key ka field rakha hai
                    OutlinedTextField(
                        value = keyInput,
                        onValueChange = { keyInput = it },
                        label = { Text("API key") },
                        singleLine = true,
                        visualTransformation = if (showKey) VisualTransformation.None else PasswordVisualTransformation(),
                        trailingIcon = {
                            TextButton(onClick = { showKey = !showKey }) {
                                Text(if (showKey) "Hide" else "Show")
                            }
                        },
                        modifier = Modifier.fillMaxWidth()
                    )

                    Text(
                        "Stored on this phone only (not encrypted).",
                        color = Ink.copy(alpha = 0.5f),
                        style = MaterialTheme.typography.bodySmall
                    )

                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Button(
                            onClick = {
                                // Baki values ko as it is bhej rahe hain taaki error na aaye
                                onSaveText(keyInput.trim(), endpoint, model, wakeWord)
                                saved = true
                            },
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text(if (saved) "Saved ✓" else "Save", color = Color.Black)
                        }

                        OutlinedButton(
                            onClick = { onTestApi(keyInput.trim(), endpoint, model) },
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text("Test API", color = Color.White)
                        }
                    }

                    if (testStatus.isNotBlank()) {
                        Text(
                            testStatus,
                            color = Ink.copy(alpha = 0.75f),
                            style = MaterialTheme.typography.bodySmall
                        )
                    }

                    SectionTitle("Voice")

                    Text(
                        "Speech language (EN-IN works best for Hinglish)",
                        color = Ink,
                        style = MaterialTheme.typography.bodyMedium
                    )

                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        LOCALES.forEach { (tag, label) ->
                            val chipModifier = Modifier.weight(1f)
                            val padding = PaddingValues(horizontal = 4.dp, vertical = 8.dp)

                            if (tag == speechLocale) {
                                Button(
                                    onClick = { onLocaleChange(tag) },
                                    modifier = chipModifier,
                                    contentPadding = padding,
                                    shape = RoundedCornerShape(10.dp)
                                ) {
                                    Text(label, style = MaterialTheme.typography.labelSmall, color = Color.Black)
                                }
                            } else {
                                OutlinedButton(
                                    onClick = { onLocaleChange(tag) },
                                    modifier = chipModifier,
                                    contentPadding = padding,
                                    shape = RoundedCornerShape(10.dp)
                                ) {
                                    Text(label, style = MaterialTheme.typography.labelSmall, color = Color.White)
                                }
                            }
                        }
                    }

                    // SPEECH SPEED SLIDER HATA DIYA HAI
                    
                    SectionTitle("Background listening")

                    SwitchRow(
                        title = "Listen for wake word",
                        subtitle = "Keeps the mic service running",
                        checked = bgOn,
                        onChange = {
                            bgOn = it
                            if (it) onStartBg() else onStopBg()
                        }
                    )

                    SwitchRow(
                        title = "Follow-up questions",
                        subtitle = "Keep listening after a reply, no wake word needed",
                        checked = followUp,
                        onChange = { followUp = it; prefs.edit().putBoolean("follow_up", it).apply() }
                    )

                    SwitchRow(
                        title = "Beep instead of \"Yes Sir\"",
                        subtitle = "Faster wake acknowledgement",
                        checked = beep,
                        onChange = { beep = it; prefs.edit().putBoolean("wake_beep", it).apply() }
                    )

                    SwitchRow(
                        title = "Keep CPU awake",
                        subtitle = "More reliable with screen off, uses more battery",
                        checked = wakeLockOn,
                        onChange = { wakeLockOn = it; prefs.edit().putBoolean("use_wakelock", it).apply() }
                    )

                    SwitchRow(
                        title = "Offer to start after reboot",
                        subtitle = "Shows a tap-to-start notification",
                        checked = onBoot,
                        onChange = { onBoot = it; prefs.edit().putBoolean("wake_on_boot", it).apply() }
                    )

                    SwitchRow(
                        title = "Bluetooth headset mic",
                        subtitle = "Experimental, may lower headset audio quality",
                        checked = btMic,
                        onChange = { btMic = it; prefs.edit().putBoolean("bt_mic", it).apply() }
                    )

                    Text(
                        "Wake word and language changes apply while listening is on. The other switches apply from the next command.",
                        color = Ink.copy(alpha = 0.5f),
                        style = MaterialTheme.typography.bodySmall
                    )

                    SectionTitle("Data")

                    OutlinedButton(
                        onClick = onClearHistory,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Text("Clear conversation history", color = Color.White)
                    }

                    Spacer(Modifier.height(4.dp))

                    TextButton(
                        onClick = { closeNow() },
                        modifier = Modifier.align(Alignment.CenterHorizontally)
                    ) {
                        Text("Close", color = Ink)
                    }
                }
            }
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Spacer(Modifier.height(8.dp))
    Text(
        text.uppercase(),
        color = Ink.copy(alpha = 0.6f),
        fontWeight = FontWeight.Bold,
        style = MaterialTheme.typography.labelMedium
    )
}

@Composable
private fun SwitchRow(
    title: String,
    subtitle: String,
    checked: Boolean,
    onChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(
            modifier = Modifier
                .weight(1f)
                .padding(end = 8.dp)
        ) {
            Text(
                title,
                color = Ink,
                style = MaterialTheme.typography.bodyLarge
            )

            Text(
                subtitle,
                color = Ink.copy(alpha = 0.55f),
                style = MaterialTheme.typography.bodySmall
            )
        }

        Switch(
            checked = checked,
            onCheckedChange = onChange
        )
    }
}
