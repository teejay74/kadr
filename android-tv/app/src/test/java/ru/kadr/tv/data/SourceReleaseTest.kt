package ru.kadr.tv.data

import org.junit.Assert.assertEquals
import org.junit.Test

class SourceReleaseTest {
    @Test
    fun `recommendation prefers quality then seeders`() {
        val sources = listOf(
            source("720", "720p", 100),
            source("1080-slow", "1080p", 5),
            source("1080-fast", "1080p", 20),
        )

        assertEquals("1080-fast", recommendedSourceId(sources))
    }

    @Test
    fun `displayed buffer progress never moves backwards`() {
        assertEquals(0.7, monotonicBufferProgress(0.7, 0.3), 0.0)
        assertEquals(0.9, monotonicBufferProgress(0.7, 0.9), 0.0)
    }

    @Test
    fun `confirmed episode is found without guessing another file`() {
        val episode = episode()
        val report = EpisodeMatchReport(
            taskId = "task",
            metadataAvailable = true,
            files = listOf(
                EpisodeMatchFile(
                    fileId = 3,
                    filePath = "S01E02.mkv",
                    episodes = listOf(identity()),
                    alternatives = emptyList(),
                    confirmed = true,
                    unsafe = false,
                ),
            ),
        )

        assertEquals(true, report.hasConfirmedEpisode(episode))
    }

    @Test
    fun `manual mapping uses selected catalog episode`() {
        val episode = episode()
        val file = EpisodeMatchFile(
            fileId = 4,
            filePath = "episode.mkv",
            episodes = emptyList(),
            alternatives = emptyList(),
            confirmed = false,
            unsafe = false,
        )

        assertEquals(episode.id, file.mappingFor(episode).single().catalogEpisodeId)
        assertEquals(episode.number, file.mappingFor(episode).single().episodeNumber)
    }

    private fun source(id: String, resolution: String, seeders: Int) = SourceRelease(
        id = id,
        sizeBytes = 1_000,
        seeders = seeders,
        resolution = resolution,
        source = "WEB-DL",
        codec = "H.264",
        hdr = false,
        language = "RU",
    )

    private fun episode() = EpisodeSummary(
        id = 202,
        seasonNumber = 1,
        number = 2,
        name = "Вторая серия",
        overview = "",
        runtimeMinutes = 48,
        rating = 8.0,
    )

    private fun identity() = EpisodeMatchIdentity(
        seasonNumber = 1,
        episodeNumber = 2,
        catalogEpisodeId = 202,
        name = "Вторая серия",
        runtimeMinutes = 48,
    )
}
