package ru.kadr.tv.ui

import org.junit.Assert.assertEquals
import org.junit.Test
import ru.kadr.tv.data.PlayedRange

class PlayedRangesTest {
    @Test
    fun seeksAndPausedPositionChangesDoNotCountAsPlayback() {
        val ranges = PlayedRanges()
        ranges.playbackChanged(true, 0)
        ranges.positionDiscontinuity(10_000, 90_000, isPlaying = true)
        ranges.playbackChanged(false, 95_000)
        ranges.positionDiscontinuity(95_000, 99_000, isPlaying = false)

        assertEquals(
            listOf(PlayedRange(0, 10_000), PlayedRange(90_000, 95_000)),
            ranges.snapshot(99_000, 100_000),
        )
    }

    @Test
    fun resumedPlaybackAndRepeatedPortionsProduceUniqueRanges() {
        val ranges = PlayedRanges()
        ranges.playbackChanged(true, 20_000)
        ranges.positionDiscontinuity(70_000, 50_000, isPlaying = true)

        assertEquals(listOf(PlayedRange(20_000, 85_000)), ranges.snapshot(85_000, 100_000))
    }
}
