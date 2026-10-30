package ru.kadr.tv.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class PlayerControlsTest {
    @Test
    fun seekPositionIsClampedToMediaBounds() {
        assertEquals(0, clampSeekPosition(-10_000, 60_000))
        assertEquals(25_000, clampSeekPosition(25_000, 60_000))
        assertEquals(60_000, clampSeekPosition(70_000, 60_000))
    }

    @Test
    fun progressFractionHandlesUnknownAndOutOfRangeValues() {
        assertEquals(0f, progressFraction(10_000, 0), 0f)
        assertEquals(0.5f, progressFraction(30_000, 60_000), 0f)
        assertEquals(1f, progressFraction(70_000, 60_000), 0f)
    }

    @Test
    fun playerTimeUsesTvFriendlyClockFormat() {
        assertEquals("0:00", formatPlayerTime(-1))
        assertEquals("2:05", formatPlayerTime(125_000))
        assertEquals("1:02:03", formatPlayerTime(3_723_000))
    }
}
