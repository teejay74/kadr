package ru.kadr.tv.data

data class Health(
    val status: String,
    val service: String,
    val version: String,
    val database: String,
)

enum class MediaKind(val apiValue: String) {
    MOVIE("movie"),
    SERIES("series"),
}

const val MAX_SEARCH_QUERY_LENGTH = 120

fun normalizeSearchInput(input: String): String = input.take(MAX_SEARCH_QUERY_LENGTH)

fun searchableQuery(input: String): String? = input.trim().takeIf { it.length >= 2 }

data class MediaCard(
    val id: Int,
    val kind: MediaKind,
    val title: String,
    val overview: String,
    val year: Int?,
    val rating: Double,
    val posterUrl: String?,
    val backdropUrl: String?,
)

data class MediaDetails(
    val card: MediaCard,
    val originalTitle: String,
    val runtimeMinutes: Int?,
    val tagline: String?,
    val genres: List<String>,
    val seasons: List<SeasonSummary>,
)

data class SeasonSummary(
    val id: Int,
    val number: Int,
    val name: String,
    val episodeCount: Int,
)

data class EpisodeSummary(
    val id: Int,
    val seasonNumber: Int,
    val number: Int,
    val name: String,
    val overview: String,
    val runtimeMinutes: Int?,
    val rating: Double,
    val stillUrl: String?,
)

data class SeasonDetails(
    val number: Int,
    val name: String,
    val overview: String,
    val episodes: List<EpisodeSummary>,
)

data class SourceRelease(
    val id: String,
    val sizeBytes: Long,
    val seeders: Int?,
    val resolution: String?,
    val source: String?,
    val codec: String?,
    val hdr: Boolean,
    val language: String?,
)

fun recommendedSourceId(sources: List<SourceRelease>): String? = sources.maxWithOrNull(
    compareBy<SourceRelease> { resolutionScore(it.resolution) }
        .thenBy { it.seeders ?: -1 }
        .thenBy { it.sizeBytes },
)?.id

fun monotonicBufferProgress(current: Double, observed: Double): Double =
    maxOf(current, observed).coerceIn(0.0, 1.0)

private fun resolutionScore(resolution: String?): Int = when (resolution?.lowercase()) {
    "2160p", "4k" -> 4
    "1080p" -> 3
    "720p" -> 2
    "576p", "480p" -> 1
    else -> 0
}

enum class PlaybackStatus {
    READY,
    BUFFERING,
    SOURCE_REQUIRED,
    UNAVAILABLE,
}

data class PlaybackResolution(
    val status: PlaybackStatus,
    val streamUrl: String?,
    val taskId: String?,
    val resumePositionSeconds: Long,
    val bufferProgress: Double,
    val message: String?,
)

data class StreamReadiness(
    val ready: Boolean,
    val bufferProgress: Double,
    val fileProgress: Double,
    val downloadSpeedBytes: Long,
)

data class EpisodeMatchIdentity(
    val seasonNumber: Int,
    val episodeNumber: Int,
    val catalogEpisodeId: Int?,
    val name: String,
    val runtimeMinutes: Int?,
)

data class EpisodeMatchFile(
    val fileId: Int,
    val filePath: String,
    val episodes: List<EpisodeMatchIdentity>,
    val alternatives: List<EpisodeMatchIdentity>,
    val confirmed: Boolean,
    val unsafe: Boolean,
)

data class EpisodeMatchReport(
    val taskId: String,
    val metadataAvailable: Boolean,
    val files: List<EpisodeMatchFile>,
)

fun EpisodeMatchReport.hasConfirmedEpisode(episode: EpisodeSummary): Boolean = files.any { file ->
    file.confirmed && file.episodes.any {
        it.seasonNumber == episode.seasonNumber && it.episodeNumber == episode.number
    }
}

fun EpisodeMatchFile.mappingFor(episode: EpisodeSummary): List<EpisodeMatchIdentity> {
    val proposed = episodes.filter {
        it.seasonNumber == episode.seasonNumber && it.episodeNumber == episode.number
    }
    return proposed.ifEmpty {
        listOf(
            EpisodeMatchIdentity(
                seasonNumber = episode.seasonNumber,
                episodeNumber = episode.number,
                catalogEpisodeId = episode.id,
                name = episode.name,
                runtimeMinutes = episode.runtimeMinutes,
            ),
        )
    }
}
