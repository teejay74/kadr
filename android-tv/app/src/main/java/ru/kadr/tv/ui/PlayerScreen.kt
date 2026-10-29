package ru.kadr.tv.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.SeekParameters
import androidx.media3.ui.PlayerView
import kotlinx.coroutines.delay

@Composable
@androidx.annotation.OptIn(UnstableApi::class)
fun PlayerScreen(
    streamUrl: String,
    resumePositionMs: Long,
    onProgress: (positionMs: Long, durationMs: Long, completed: Boolean, final: Boolean) -> Unit,
) {
    val context = LocalContext.current
    val rootView = LocalView.current
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
    LaunchedEffect(player) {
        while (true) {
            delay(PROGRESS_INTERVAL_MS)
            if (player.playbackState != Player.STATE_ENDED) {
                onProgress(player.currentPosition, player.duration, false, false)
            }
        }
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
    Box(Modifier.fillMaxSize().background(Color.Black)) {
        AndroidView(
            factory = { viewContext ->
                PlayerView(viewContext).apply {
                    this.player = player
                    useController = true
                    controllerAutoShow = true
                    controllerShowTimeoutMs = 5_000
                    keepScreenOn = true
                    isFocusable = true
                    isFocusableInTouchMode = true
                    requestFocus()
                }
            },
            update = { it.player = player },
            modifier = Modifier.fillMaxSize(),
        )
    }
}

private const val SEEK_INCREMENT_MS = 10_000L
private const val PROGRESS_INTERVAL_MS = 5_000L
