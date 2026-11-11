package ru.kadr.tv.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class EpisodeNavigationTest {
    @Test
    fun selectsTheNextNumberedEpisodeRegardlessOfProviderOrder() {
        val current = episode(2)
        val episodes = listOf(episode(5), episode(1), current, episode(3))

        assertEquals(3, nextEpisodeInSeason(current, episodes)?.number)
        assertNull(nextEpisodeInSeason(episode(5), episodes))
    }

    @Test
    fun crossesToTheNearestFollowingSeason() {
        val seasons = listOf(season(4), season(1), season(3))

        assertEquals(3, nextSeasonNumber(1, seasons))
        assertNull(nextSeasonNumber(4, seasons))
    }

    private fun episode(number: Int) = EpisodeSummary(
        id = 100 + number,
        seasonNumber = 1,
        number = number,
        name = "Episode $number",
        overview = "",
        runtimeMinutes = 45,
        rating = 0.0,
        stillUrl = null,
    )

    private fun season(number: Int) = SeasonSummary(
        id = number,
        number = number,
        name = "Season $number",
        episodeCount = 10,
    )
}
