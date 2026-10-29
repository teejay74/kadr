package ru.kadr.tv.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

class ApiException(
    val statusCode: Int,
    val code: String,
    override val message: String,
) : IOException(message)

class KadrApi(private val serverUrl: String) {
    suspend fun health(): Health = request("/api/v1/system/health") { body ->
        Health(
            status = body.getString("status"),
            service = body.getString("service"),
            version = body.getString("version"),
            database = body.getString("database"),
        )
    }

    suspend fun popular(kind: MediaKind): List<MediaCard> =
        request("/api/v1/${kindPath(kind)}?page=1&sort=popular") { body ->
            body.getJSONArray("items").mapObjects { parseCard(it) }
        }

    suspend fun search(kind: MediaKind, query: String): List<MediaCard> {
        val encoded = URLEncoder.encode(query.trim(), Charsets.UTF_8.name())
        return request("/api/v1/${kindPath(kind)}/search?q=$encoded&page=1") { body ->
            body.getJSONArray("items").mapObjects { parseCard(it) }
        }
    }

    suspend fun details(kind: MediaKind, mediaId: Int): MediaDetails =
        request("/api/v1/${kindPath(kind)}/$mediaId") { body ->
            MediaDetails(
                card = parseCard(body),
                originalTitle = body.optString("original_title"),
                runtimeMinutes = body.optNullableInt("runtime_minutes"),
                tagline = body.optNullableString("tagline"),
                genres = body.optJSONArray("genres")?.mapObjects { it.getString("name") }.orEmpty(),
                seasons = body.optJSONArray("seasons")?.mapObjects { item ->
                    SeasonSummary(
                        id = item.getInt("id"),
                        number = item.getInt("number"),
                        name = item.getString("name"),
                        episodeCount = item.getInt("episode_count"),
                    )
                }.orEmpty(),
            )
        }

    suspend fun season(seriesId: Int, seasonNumber: Int): SeasonDetails = request(
        "/api/v1/series/$seriesId/seasons/$seasonNumber",
    ) { body ->
        SeasonDetails(
            number = body.getInt("number"),
            name = body.getString("name"),
            overview = body.optString("overview"),
            episodes = body.getJSONArray("episodes").mapObjects { item ->
                EpisodeSummary(
                    id = item.getInt("id"),
                    seasonNumber = item.getInt("season_number"),
                    number = item.getInt("number"),
                    name = item.getString("name"),
                    overview = item.optString("overview"),
                    runtimeMinutes = item.optNullableInt("runtime_minutes"),
                    rating = item.optDouble("rating", 0.0),
                )
            },
        )
    }

    suspend fun resolveMovie(mediaId: Int): PlaybackResolution = request(
        path = "/api/v1/playback/resolve",
        method = "POST",
        requestBody = JSONObject()
            .put("media_kind", "movie")
            .put("media_id", mediaId)
            .put("profile_key", "android-tv")
            .toString(),
    ) { parsePlayback(it) }

    suspend fun resolveEpisode(mediaId: Int, episode: EpisodeSummary): PlaybackResolution = request(
        path = "/api/v1/playback/resolve",
        method = "POST",
        requestBody = JSONObject()
            .put("media_kind", "series")
            .put("media_id", mediaId)
            .put("season_number", episode.seasonNumber)
            .put("episode_number", episode.number)
            .put("catalog_episode_id", episode.id)
            .put("profile_key", "android-tv")
            .toString(),
    ) { parsePlayback(it) }

    suspend fun streamReadiness(taskId: String): StreamReadiness = request(
        "/api/v1/torrents/$taskId/stream/readiness",
    ) { body ->
        StreamReadiness(
            ready = body.getBoolean("ready"),
            bufferProgress = body.optDouble("buffer_progress", 0.0),
            fileProgress = body.optDouble("file_progress", 0.0),
            downloadSpeedBytes = body.optLong("download_speed_bytes", 0),
        )
    }

    suspend fun sources(
        mediaId: Int,
        kind: MediaKind,
        seasonNumber: Int? = null,
    ): List<SourceRelease> = request(
        buildString {
            append("/api/v1/media/$mediaId/sources?kind=${kind.apiValue}&sort=seeders&order=desc")
            if (seasonNumber != null) append("&season_number=$seasonNumber")
        },
    ) { body ->
        body.getJSONArray("items").mapObjects { item ->
            SourceRelease(
                id = item.getString("id"),
                sizeBytes = item.getLong("size_bytes"),
                seeders = item.optNullableInt("seeders"),
                resolution = item.optNullableString("resolution"),
                source = item.optNullableString("source"),
                codec = item.optNullableString("codec"),
                hdr = item.optBoolean("hdr", false),
                language = item.optNullableString("language"),
            )
        }
    }

    suspend fun addSource(
        mediaId: Int,
        kind: MediaKind,
        sourceId: String,
        seasonNumber: Int? = null,
    ): String = request(
            path = "/api/v1/media/$mediaId/torrents",
            method = "POST",
            requestBody = JSONObject()
                .put("media_kind", kind.apiValue)
                .put("source_id", sourceId)
                .apply { if (seasonNumber != null) put("season_number", seasonNumber) }
                .toString(),
        ) { it.getString("id") }

    suspend fun hasVideoFiles(taskId: String): Boolean = requestArray(
        "/api/v1/torrents/$taskId/files",
    ) { items -> items.mapObjects { it }.any { it.optBoolean("is_video", false) } }

    suspend fun analyzeEpisodeMatches(taskId: String): EpisodeMatchReport = request(
        path = "/api/v1/torrents/$taskId/episode-matches/analyze",
        method = "POST",
    ) { parseEpisodeMatchReport(it) }

    suspend fun confirmEpisodeMatch(
        taskId: String,
        file: EpisodeMatchFile,
        episode: EpisodeSummary,
    ): EpisodeMatchReport = request(
        path = "/api/v1/torrents/$taskId/episode-matches",
        method = "PUT",
        requestBody = JSONObject().put(
            "mappings",
            JSONArray().put(
                JSONObject()
                    .put("file_id", file.fileId)
                    .put(
                        "episodes",
                        JSONArray(file.mappingFor(episode).map { identity ->
                            JSONObject()
                                .put("season_number", identity.seasonNumber)
                                .put("episode_number", identity.episodeNumber)
                                .put("catalog_episode_id", identity.catalogEpisodeId)
                                .put("name", identity.name)
                                .put("runtime_minutes", identity.runtimeMinutes)
                        }),
                    ),
            ),
        ).toString(),
    ) { parseEpisodeMatchReport(it) }

    private suspend fun <T> request(
        path: String,
        method: String = "GET",
        requestBody: String? = null,
        parser: (JSONObject) -> T,
    ): T = requestPayload(path, method, requestBody) { parser(JSONObject(it)) }

    private suspend fun <T> requestArray(
        path: String,
        parser: (JSONArray) -> T,
    ): T = requestPayload(path) { parser(JSONArray(it)) }

    private suspend fun <T> requestPayload(
        path: String,
        method: String = "GET",
        requestBody: String? = null,
        parser: (String) -> T,
    ): T = withContext(Dispatchers.IO) {
        val connection = URL(ServerAddress.resolve(serverUrl, path)).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = CONNECT_TIMEOUT_MS
            connection.readTimeout = READ_TIMEOUT_MS
            connection.setRequestProperty("Accept", "application/json")
            if (requestBody != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json")
                connection.outputStream.bufferedWriter(Charsets.UTF_8).use { it.write(requestBody) }
            }
            val status = connection.responseCode
            val response = (if (status in 200..299) connection.inputStream else connection.errorStream)
                ?.bufferedReader(Charsets.UTF_8)
                ?.use { it.readText() }
                .orEmpty()
            if (status !in 200..299) {
                val error = runCatching { JSONObject(response) }.getOrNull()
                throw ApiException(
                    statusCode = status,
                    code = error?.optString("code", "request_failed") ?: "request_failed",
                    message = error?.optString("message", "Ошибка запроса к KADR") ?: "Ошибка запроса к KADR",
                )
            }
            parser(response)
        } finally {
            connection.disconnect()
        }
    }

    private fun kindPath(kind: MediaKind): String = when (kind) {
        MediaKind.MOVIE -> "movies"
        MediaKind.SERIES -> "series"
    }

    private fun parseCard(body: JSONObject): MediaCard = MediaCard(
        id = body.getInt("id"),
        kind = when (body.getString("kind")) {
            "series" -> MediaKind.SERIES
            else -> MediaKind.MOVIE
        },
        title = body.getString("title"),
        overview = body.optString("overview"),
        year = body.optNullableInt("year"),
        rating = body.optDouble("rating", 0.0),
        posterUrl = body.optNullableString("poster_url"),
        backdropUrl = body.optNullableString("backdrop_url"),
    )

    private fun parsePlayback(body: JSONObject): PlaybackResolution = PlaybackResolution(
        status = PlaybackStatus.valueOf(body.getString("status").uppercase()),
        streamUrl = body.optNullableString("stream_url")?.let { ServerAddress.resolve(serverUrl, it) },
        taskId = body.optNullableString("task_id"),
        resumePositionSeconds = body.optLong("resume_position_seconds", 0),
        bufferProgress = body.optDouble("buffer_progress", 0.0),
        message = body.optNullableString("message"),
    )

    private fun parseEpisodeMatchReport(body: JSONObject): EpisodeMatchReport = EpisodeMatchReport(
        taskId = body.getString("task_id"),
        metadataAvailable = body.optBoolean("metadata_available", false),
        files = body.getJSONArray("files").mapObjects { file ->
            EpisodeMatchFile(
                fileId = file.getInt("file_id"),
                filePath = file.getString("file_path"),
                episodes = file.getJSONArray("episodes").mapObjects { parseEpisodeIdentity(it) },
                alternatives = file.getJSONArray("alternatives").mapObjects { parseEpisodeIdentity(it) },
                confirmed = file.optBoolean("confirmed", false),
                unsafe = file.optBoolean("unsafe", false),
            )
        },
    )

    private fun parseEpisodeIdentity(body: JSONObject): EpisodeMatchIdentity = EpisodeMatchIdentity(
        seasonNumber = body.getInt("season_number"),
        episodeNumber = body.getInt("episode_number"),
        catalogEpisodeId = body.optNullableInt("catalog_episode_id"),
        name = body.optString("name"),
        runtimeMinutes = body.optNullableInt("runtime_minutes"),
    )

    private fun JSONObject.optNullableString(key: String): String? =
        if (isNull(key)) null else optString(key).takeIf { it.isNotBlank() }

    private fun JSONObject.optNullableInt(key: String): Int? =
        if (isNull(key) || !has(key)) null else getInt(key)

    private fun <T> JSONArray.mapObjects(transform: (JSONObject) -> T): List<T> =
        List(length()) { index -> transform(getJSONObject(index)) }

    private companion object {
        const val CONNECT_TIMEOUT_MS = 8_000
        const val READ_TIMEOUT_MS = 15_000
    }
}
