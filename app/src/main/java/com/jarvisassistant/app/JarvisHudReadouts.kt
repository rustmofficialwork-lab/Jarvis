package com.jarvisassistant.app

import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlinx.coroutines.delay

/** Corner readouts (name, state, power, clock) like the film HUD. */
@Composable
fun JarvisHudReadouts(state: JarvisState, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    var time by remember { mutableStateOf("") }
    var date by remember { mutableStateOf("") }
    var power by remember { mutableStateOf("PWR --") }

    LaunchedEffect(Unit) {
        val tf = SimpleDateFormat("HH:mm:ss", Locale.getDefault())
        val df = SimpleDateFormat("EEE, d MMM yyyy", Locale.getDefault())
        while (true) {
            val now = Date()
            time = tf.format(now)
            date = df.format(now)
            val i = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
            val lvl = i?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
            val sc = i?.getIntExtra(BatteryManager.EXTRA_SCALE, 100) ?: 100
            val st = i?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
            val chg = st == BatteryManager.BATTERY_STATUS_CHARGING || st == BatteryManager.BATTERY_STATUS_FULL
            power = if (lvl >= 0) "PWR ${lvl * 100 / sc}%" + (if (chg) " +" else "") else "PWR --"
            delay(1000)
        }
    }

    val cyan = Color(0xFF29D9FF)
    Row(
        modifier = modifier.fillMaxWidth().padding(top = 36.dp, start = 20.dp, end = 20.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Column {
            Text("J.A.R.V.I.S.", color = cyan, fontFamily = FontFamily.Monospace, fontSize = 13.sp)
            Text("STATE ${state.name}", color = cyan.copy(alpha = 0.7f), fontFamily = FontFamily.Monospace, fontSize = 11.sp)
            Text(power, color = cyan.copy(alpha = 0.7f), fontFamily = FontFamily.Monospace, fontSize = 11.sp)
        }
        Column(horizontalAlignment = Alignment.End) {
            Text(time, color = cyan, fontFamily = FontFamily.Monospace, fontSize = 13.sp)
            Text(date, color = cyan.copy(alpha = 0.7f), fontFamily = FontFamily.Monospace, fontSize = 11.sp)
        }
    }
}
