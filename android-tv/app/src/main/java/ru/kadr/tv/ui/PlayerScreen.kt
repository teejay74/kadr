package ru.kadr.tv.ui

import android.view.KeyEvent
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.SeekParameters
import androidx.media3.ui.PlayerView
import androidx.tv.material3.Text
import kotlinx.coroutines.delay

@Composable
@androidx.annotation.OptIn(UnstableApi::class)
fun PlayerScreen(
    streamUrl: String,
    resumePositionMs: Long,
    title: String,
    episodeLabel: String?,
    onProgress: (positionMs: Long, durationMs: Long, completed: Boolean, final: Boolean) -> Unit,
) {
    val context = LocalContext.current
    val rootView = LocalView.current
    val focusRequester = remember { FocusRequester() }
    val player = remember(streamUrl) {
        ExoPlayer.Builder(context)
            .setSeekBackIncrementMs(SEEK_INCREMENT_MS)
            .setSeekForwardIncrementMs(SEEK_INCREMENT_MS)
            .build().apply {
                setSeekParameters(SeekParameters.CLOSEST_SYNC)
                setMediaItem(MediaItem.fromUri(streamUrl), resumePositionMs)
                prepare()
                playWhenReady = true
            }
    }
    var controlsVisible by remember { mutableStateOf(true) }
    var interactionVersion by remember { mutableIntStateOf(0) }
    var positionMs by remember { mutableLongStateOf(resumePositionMs) }
    var durationMs by remember { mutableLongStateOf(0L) }
    var bufferedPositionMs by remember { mutableLongStateOf(0L) }
    var seekTargetMs by remember { mutableStateOf<Long?>(null) }
    var isPlaying by remember { mutableStateOf(true) }
    var isBuffering by remember { mutableStateOf(true) }

    fun revealControls() {
        controlsVisible = true
        interactionVersion += 1
    }

    fun queueSeek(deltaMs: Long) {
        revealControls()
        val base = seekTargetMs ?: player.currentPosition
        seekTargetMs = clampSeekPosition(base + deltaMs, player.duration)
    }

    LaunchedEffect(Unit) { focusRequester.requestFocus() }
    LaunchedEffect(player) {
        while (true) {
            positionMs = player.currentPosition.coerceAtLeast(0)
            durationMs = validDuration(player.duration)
            bufferedPositionMs = player.bufferedPosition.coerceAtLeast(0)
            isPlaying = player.isPlaying
            isBuffering = player.playbackState == Player.STATE_BUFFERING
            delay(PLAYER_UI_UPDATE_MS)
        }
    }
    LaunchedEffect(player) {
        while (true) {
            delay(PROGRESS_INTERVAL_MS)
            if (player.playbackState != Player.STATE_ENDED) {
                onProgress(player.currentPosition, player.duration, false, false)
            }
        }
    }
    LaunchedEffect(seekTargetMs) {
        val target = seekTargetMs ?: return@LaunchedEffect
        delay(SEEK_COMMIT_DELAY_MS)
        player.seekTo(target)
        positionMs = target
        seekTargetMs = null
    }
    LaunchedEffect(controlsVisible, interactionVersion, isPlaying, seekTargetMs) {
        if (!controlsVisible || !isPlaying || seekTargetMs != null) return@LaunchedEffect
        delay(CONTROLS_TIMEOUT_MS)
        controlsVisible = false
    }
    DisposableEffect(player, rootView) {
        var completed = false
        val listener = object : Player.Listener {
            override fun onPlaybackStateChanged(playbackState: Int) {
                if (playbackState == Player.STATE_ENDED && !completed) {
                    completed = true
                    onProgress(0, player.duration, true, true)
                }
            }
        }
        player.addListener(listener)
        val previousKeepScreenOn = rootView.keepScreenOn
        rootView.keepScreenOn = true
        onDispose {
            if (!completed) onProgress(player.currentPosition, player.duration, false, true)
            rootView.keepScreenOn = previousKeepScreenOn
            player.removeListener(listener)
            player.release()
        }
    }

    BackHandler(enabled = controlsVisible) {
        controlsVisible = false
        seekTargetMs = null
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black)
            .focusRequester(focusRequester)
            .onPreviewKeyEvent { event ->
                val native = event.nativeKeyEvent
                when (native.keyCode) {
                    KeyEvent.KEYCODE_DPAD_LEFT -> {
                        if (native.action == KeyEvent.ACTION_DOWN) queueSeek(-SEEK_INCREMENT_MS)
                        true
                    }
                    KeyEvent.KEYCODE_DPAD_RIGHT -> {
                        if (native.action == KeyEvent.ACTION_DOWN) queueSeek(SEEK_INCREMENT_MS)
                        true
                    }
                    KeyEvent.KEYCODE_DPAD_UP -> {
                        if (native.action == KeyEvent.ACTION_DOWN) revealControls()
                        true
                    }
                    KeyEvent.KEYCODE_DPAD_DOWN -> {
                        if (native.action == KeyEvent.ACTION_DOWN) controlsVisible = false
                        true
                    }
                    KeyEvent.KEYCODE_DPAD_CENTER,
                    KeyEvent.KEYCODE_ENTER,
                    KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE -> {
                        if (native.action == KeyEvent.ACTION_DOWN && native.repeatCount == 0) {
                            val target = seekTargetMs
                            if (target != null) {
                                player.seekTo(target)
                                seekTargetMs = null
                            } else if (player.isPlaying) {
                                player.pause()
                            } else {
                                player.play()
                            }
                            revealControls()
                        }
                        true
                    }
                    KeyEvent.KEYCODE_MEDIA_PLAY -> {
                        if (native.action == KeyEvent.ACTION_DOWN) player.play()
                        revealControls()
                        true
                    }
                    KeyEvent.KEYCODE_MEDIA_PAUSE -> {
                        if (native.action == KeyEvent.ACTION_DOWN) player.pause()
                        revealControls()
                        true
                    }
                    else -> false
                }
            }
            .focusable(),
    ) {
        AndroidView(
            factory = { viewContext ->
                PlayerView(viewContext).apply {
                    this.player = player
                    useController = false
                    keepScreenOn = true
                    isFocusable = false
                }
            },
            update = { it.player = player },
            modifier = Modifier.fillMaxSize(),
        )
        if (controlsVisible) {
            TvPlayerOverlay(
                title = title,
                episodeLabel = episodeLabel,
                positionMs = seekTargetMs ?: positionMs,
                durationMs = durationMs,
                bufferedPositionMs = bufferedPositionMs,
                isPlaying = isPlaying,
                isBuffering = isBuffering,
                isSeeking = seekTargetMs != null,
            )
        }
    }
}

@Composable
private fun TvPlayerOverlay(
    title: String,
    episodeLabel: String?,
    positionMs: Long,
    durationMs: Long,
    bufferedPositionMs: Long,
    isPlaying: Boolean,
    isBuffering: Boolean,
    isSeeking: Boolean,
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    listOf(Color(0xAA000000), Color.Transparent, Color(0xDD000000)),
                ),
            ),
    ) {
        Column(modifier = Modifier.align(Alignment.TopStart).padding(horizontal = 56.dp, vertical = 40.dp)) {
            Text(title, color = Color.White, fontSize = 30.sp, fontWeight = FontWeight.Bold)
            episodeLabel?.let {
                Text(it, color = Color(0xFFD4D4D8), fontSize = 18.sp, modifier = Modifier.padding(top = 6.dp))
            }
        }
        Column(
            modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(horizontal = 56.dp, vertical = 42.dp),
        ) {
            if (isBuffering) {
                Text("Буферизация…", color = Color.White, fontSize = 18.sp, modifier = Modifier.padding(bottom = 14.dp))
            } else if (isSeeking) {
                Text(
                    "Перемотка: ${formatPlayerTime(positionMs)}",
                    color = Color.White,
                    fontSize = 18.sp,
                    modifier = Modifier.padding(bottom = 14.dp),
                )
            }
            PlayerProgressBar(positionMs, bufferedPositionMs, durationMs)
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 18.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(formatPlayerTime(positionMs), color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                Text(" / ${formatPlayerTime(durationMs)}", color = Color(0xFFB4B4BD), fontSize = 18.sp)
                Spacer(Modifier.weight(1f))
                PlayerHint("←", "−10 сек")
                Spacer(Modifier.width(22.dp))
                PlayerHint(if (isPlaying) "Ⅱ" else "▶", "OK")
                Spacer(Modifier.width(22.dp))
                PlayerHint("→", "+10 сек")
            }
        }
    }
}

@Composable
private fun PlayerProgressBar(positionMs: Long, bufferedPositionMs: Long, durationMs: Long) {
    val played = progressFraction(positionMs, durationMs)
    val buffered = progressFraction(bufferedPositionMs, durationMs)
    Box(
        modifier = Modifier.fillMaxWidth().height(10.dp).background(Color(0x55FFFFFF), RoundedCornerShape(5.dp)),
    ) {
        Box(
            Modifier.fillMaxHeight().fillMaxWidth(buffered).background(Color(0x88FFFFFF), RoundedCornerShape(5.dp)),
        )
        Box(
            Modifier.fillMaxHeight().fillMaxWidth(played).background(Color(0xFF8B5CF6), RoundedCornerShape(5.dp)),
        )
    }
}

@Composable
private fun PlayerHint(symbol: String, label: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(
            modifier = Modifier
                .background(Color(0x44FFFFFF), RoundedCornerShape(8.dp))
                .padding(horizontal = 10.dp, vertical = 6.dp),
            contentAlignment = Alignment.Center,
        ) {
            Text(symbol, color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Bold)
        }
        Text(label, color = Color(0xFFD4D4D8), fontSize = 15.sp)
    }
}

internal fun clampSeekPosition(positionMs: Long, durationMs: Long): Long {
    val maximum = validDuration(durationMs).takeIf { it > 0 } ?: Long.MAX_VALUE
    return positionMs.coerceIn(0, maximum)
}

internal fun progressFraction(positionMs: Long, durationMs: Long): Float =
    if (durationMs > 0) (positionMs.toDouble() / durationMs).coerceIn(0.0, 1.0).toFloat() else 0f

internal fun formatPlayerTime(milliseconds: Long): String {
    val seconds = milliseconds.coerceAtLeast(0) / 1_000
    return if (seconds >= 3_600) {
        "%d:%02d:%02d".format(seconds / 3_600, seconds / 60 % 60, seconds % 60)
    } else {
        "%d:%02d".format(seconds / 60, seconds % 60)
    }
}

private fun validDuration(durationMs: Long): Long =
    durationMs.takeUnless { it == C.TIME_UNSET || it < 0 } ?: 0

private const val SEEK_INCREMENT_MS = 10_000L
private const val SEEK_COMMIT_DELAY_MS = 450L
private const val PLAYER_UI_UPDATE_MS = 250L
private const val PROGRESS_INTERVAL_MS = 5_000L
private const val CONTROLS_TIMEOUT_MS = 5_000L
