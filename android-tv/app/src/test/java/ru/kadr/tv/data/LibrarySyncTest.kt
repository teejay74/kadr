package ru.kadr.tv.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LibrarySyncTest {
    @Test
    fun savedEpisodeMatchesOnlyItsOwnHistoryEntry() {
        val saved = savedEpisode()

        assertTrue(historyEpisode().matches(saved))
        assertFalse(historyEpisode(episodeNumber = 4).matches(saved))
        assertFalse(historyEpisode(mediaId = 99).matches(saved))
    }

    @Test
    fun progressPercentIsBoundedAndHandlesUnknownDuration() {
        assertEquals(25, historyEpisode(positionSeconds = 300, durationSeconds = 1_200).progressPercent())
        assertEquals(100, historyEpisode(positionSeconds = 1_300, durationSeconds = 1_200).progressPercent())
        assertEquals(0, historyEpisode(positionSeconds = 300, durationSeconds = 0).progressPercent())
    }

    private fun savedEpisode() = SavedLibraryItem(
        id = "saved-1",
        taskId = "task-1",
        mediaId = 42,
        mediaKind = MediaKind.SERIES,
        title = "Сериал",
        originalTitle = "Series",
        posterUrl = null,
        backdropUrl = null,
        sizeBytes = 1_024,
        streamUrl = "http://kadr/api/v1/library/saved-1/stream",
        seasonNumber = 2,
        episodeNumber = 3,
        catalogEpisodeId = 203,
    )

    private fun historyEpisode(
        mediaId: Int = 42,
        episodeNumber: Int = 3,
        positionSeconds: Long = 300,
        durationSeconds: Long = 1_200,
    ) = HistoryItem(
        mediaId = mediaId,
        mediaKind = MediaKind.SERIES,
        title = "Сериал",
        posterUrl = null,
        seasonNumber = 2,
        episodeNumber = episodeNumber,
        catalogEpisodeId = 200 + episodeNumber,
        positionSeconds = positionSeconds,
        durationSeconds = durationSeconds,
        completed = false,
    )
}
