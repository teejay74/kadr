package ru.kadr.tv.ui

import androidx.media3.common.C
import androidx.media3.common.PlaybackException
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.HttpDataSource.HttpDataSourceException
import androidx.media3.datasource.HttpDataSource.InvalidResponseCodeException
import androidx.media3.exoplayer.upstream.DefaultLoadErrorHandlingPolicy
import androidx.media3.exoplayer.upstream.LoadErrorHandlingPolicy.LoadErrorInfo

// Allow the default 30-second KADR piece wait to finish before the client times out.
internal const val TORRENT_HTTP_READ_TIMEOUT_MS = 45_000
private const val MAX_CONSECUTIVE_RETRIES = 4
private const val RETRY_STEP_MS = 2_000L

@androidx.annotation.OptIn(UnstableApi::class)
internal class TorrentLoadErrorPolicy : DefaultLoadErrorHandlingPolicy(MAX_CONSECUTIVE_RETRIES) {
    override fun getRetryDelayMsFor(loadErrorInfo: LoadErrorInfo): Long =
        torrentRetryDelayMs(loadErrorInfo.exception, loadErrorInfo.errorCount)
}

internal fun torrentRetryDelayMs(error: Throwable, errorCount: Int): Long =
    if (errorCount in 1..MAX_CONSECUTIVE_RETRIES && isTransientTorrentLoadError(error)) {
        errorCount * RETRY_STEP_MS
    } else {
        C.TIME_UNSET
    }

@androidx.annotation.OptIn(UnstableApi::class)
internal fun isTransientTorrentLoadError(error: Throwable): Boolean {
    val httpError = generateSequence(error) { it.cause }.filterIsInstance<HttpDataSourceException>().firstOrNull()
    return when (httpError) {
        is InvalidResponseCodeException -> httpError.responseCode in 502..504
        else -> httpError?.reason == PlaybackException.ERROR_CODE_IO_NETWORK_CONNECTION_TIMEOUT ||
            httpError?.reason == PlaybackException.ERROR_CODE_IO_NETWORK_CONNECTION_FAILED
    }
}
