package ru.kadr.tv.ui

import ru.kadr.tv.data.PlayedRange

internal class PlayedRanges {
    private var playingFromMs: Long? = null
    private val closed = mutableListOf<PlayedRange>()

    fun playbackChanged(isPlaying: Boolean, positionMs: Long) {
        if (isPlaying) {
            playingFromMs = playingFromMs ?: positionMs
        } else {
            closeAt(positionMs)
        }
    }

    fun positionDiscontinuity(oldPositionMs: Long, newPositionMs: Long, isPlaying: Boolean) {
        closeAt(oldPositionMs)
        playbackChanged(isPlaying, newPositionMs)
    }

    fun snapshot(positionMs: Long, durationMs: Long): List<PlayedRange> {
        val ranges = closed + listOfNotNull(activeRange(positionMs))
        val merged = mutableListOf<PlayedRange>()
        for (range in ranges.sortedBy { it.startMs }) {
            val start = range.startMs.coerceAtLeast(0)
            val end = range.endMs.coerceAtMost(durationMs)
            if (end <= start) continue
            val previous = merged.lastOrNull()
            if (previous != null && start <= previous.endMs) {
                merged[merged.lastIndex] = previous.copy(endMs = maxOf(previous.endMs, end))
            } else {
                merged += PlayedRange(start, end)
            }
        }
        return merged.take(256)
    }

    private fun closeAt(positionMs: Long) {
        activeRange(positionMs)?.let { closed += it }
        playingFromMs = null
    }

    private fun activeRange(positionMs: Long): PlayedRange? {
        val start = playingFromMs ?: return null
        return if (positionMs > start) PlayedRange(start, positionMs) else null
    }
}
