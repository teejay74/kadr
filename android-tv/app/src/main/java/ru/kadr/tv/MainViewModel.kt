package ru.kadr.tv

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import ru.kadr.tv.data.KadrApi
import ru.kadr.tv.data.EpisodeMatchFile
import ru.kadr.tv.data.EpisodeSummary
import ru.kadr.tv.data.MediaCard
import ru.kadr.tv.data.MediaDetails
import ru.kadr.tv.data.MediaKind
import ru.kadr.tv.data.PlaybackResolution
import ru.kadr.tv.data.PlaybackStatus
import ru.kadr.tv.data.ServerAddress
import ru.kadr.tv.data.ServerStore
import ru.kadr.tv.data.SeasonDetails
import ru.kadr.tv.data.SourceRelease
import ru.kadr.tv.data.monotonicBufferProgress
import ru.kadr.tv.data.recommendedSourceId
import ru.kadr.tv.data.hasConfirmedEpisode

enum class Screen {
    SETUP,
    CATALOG,
    DETAILS,
    EPISODES,
    SOURCES,
    MATCH_FILES,
    PREPARING,
    PLAYER,
}

data class UiState(
    val screen: Screen = Screen.SETUP,
    val serverUrl: String? = null,
    val movies: List<MediaCard> = emptyList(),
    val series: List<MediaCard> = emptyList(),
    val selected: MediaDetails? = null,
    val selectedSeasonNumber: Int? = null,
    val seasonDetails: SeasonDetails? = null,
    val selectedEpisode: EpisodeSummary? = null,
    val sources: List<SourceRelease> = emptyList(),
    val recommendedSourceId: String? = null,
    val episodeMatchFiles: List<EpisodeMatchFile> = emptyList(),
    val episodeMatchTaskId: String? = null,
    val playerUrl: String? = null,
    val resumePositionMs: Long = 0,
    val loading: Boolean = false,
    val message: String? = null,
)

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val serverStore = ServerStore(application)
    private var api: KadrApi? = null
    private var playbackJob: Job? = null
    private val mutableState = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = mutableState.asStateFlow()

    init {
        val saved = serverStore.read()
        if (saved != null) connect(saved)
    }

    fun connect(input: String) {
        val normalized = runCatching { ServerAddress.normalize(input) }
            .getOrElse {
                mutableState.value = UiState(screen = Screen.SETUP, message = it.message)
                return
            }
        mutableState.value = mutableState.value.copy(loading = true, message = null)
        viewModelScope.launch {
            runCatching {
                val candidate = KadrApi(normalized)
                val health = candidate.health()
                require(health.status == "ok" && health.database == "ok") {
                    "Сервер ответил, но база KADR недоступна"
                }
                serverStore.save(normalized)
                api = candidate
                val (movies, series) = loadCatalog(candidate)
                mutableState.value = UiState(
                    screen = Screen.CATALOG,
                    serverUrl = normalized,
                    movies = movies,
                    series = series,
                )
            }.onFailure { reason ->
                mutableState.value = UiState(
                    screen = Screen.SETUP,
                    serverUrl = normalized,
                    message = reason.message ?: "Не удалось подключиться к KADR",
                )
            }
        }
    }

    fun retryCatalog() {
        val currentApi = api ?: return
        mutableState.value = mutableState.value.copy(loading = true, message = null)
        viewModelScope.launch {
            runCatching { loadCatalog(currentApi) }
                .onSuccess { (movies, series) ->
                    mutableState.value = mutableState.value.copy(
                        screen = Screen.CATALOG,
                        movies = movies,
                        series = series,
                        loading = false,
                    )
                }
                .onFailure { reason ->
                    mutableState.value = mutableState.value.copy(
                        loading = false,
                        message = reason.message ?: "Не удалось загрузить каталог",
                    )
                }
        }
    }

    fun openMedia(media: MediaCard) {
        val currentApi = api ?: return
        mutableState.value = mutableState.value.copy(loading = true, message = null)
        viewModelScope.launch {
            runCatching { currentApi.details(media.kind, media.id) }
                .onSuccess { details ->
                    mutableState.value = mutableState.value.copy(
                        screen = Screen.DETAILS,
                        selected = details,
                        selectedSeasonNumber = null,
                        seasonDetails = null,
                        selectedEpisode = null,
                        sources = emptyList(),
                        recommendedSourceId = null,
                        episodeMatchFiles = emptyList(),
                        episodeMatchTaskId = null,
                        loading = false,
                    )
                }
                .onFailure { reason ->
                    mutableState.value = mutableState.value.copy(
                        loading = false,
                        message = reason.message ?: "Не удалось открыть карточку",
                    )
                }
        }
    }

    fun playSelected() {
        val currentApi = api ?: return
        val selected = mutableState.value.selected ?: return
        if (selected.card.kind != MediaKind.MOVIE) {
            openEpisodes()
            return
        }
        playbackJob?.cancel()
        mutableState.value = mutableState.value.copy(loading = true, message = null)
        playbackJob = viewModelScope.launch {
            try {
                val playback = currentApi.resolveMovie(selected.card.id)
                when (playback.status) {
                    PlaybackStatus.READY -> openPlayer(playback)
                    PlaybackStatus.BUFFERING -> waitForStreamReady(currentApi, playback)
                    PlaybackStatus.SOURCE_REQUIRED -> loadSources(currentApi, selected.card.id, MediaKind.MOVIE)
                    PlaybackStatus.UNAVAILABLE -> loadSources(currentApi, selected.card.id, MediaKind.MOVIE)
                }
            } catch (reason: CancellationException) {
                throw reason
            } catch (reason: Exception) {
                mutableState.value = mutableState.value.copy(
                    loading = false,
                    message = reason.message ?: "Не удалось подготовить воспроизведение",
                )
            }
        }
    }

    fun openEpisodes() {
        val selected = mutableState.value.selected ?: return
        if (selected.card.kind != MediaKind.SERIES) return
        val seasonNumber = selected.seasons.firstOrNull { it.number > 0 }?.number
            ?: selected.seasons.firstOrNull()?.number
        if (seasonNumber == null) {
            mutableState.value = mutableState.value.copy(message = "Для сериала не найдены сезоны")
            return
        }
        selectSeason(seasonNumber)
    }

    fun selectSeason(seasonNumber: Int) {
        val currentApi = api ?: return
        val selected = mutableState.value.selected ?: return
        playbackJob?.cancel()
        mutableState.value = mutableState.value.copy(
            screen = Screen.EPISODES,
            selectedSeasonNumber = seasonNumber,
            seasonDetails = null,
            selectedEpisode = null,
            loading = true,
            message = null,
        )
        playbackJob = viewModelScope.launch {
            try {
                val season = currentApi.season(selected.card.id, seasonNumber)
                mutableState.value = mutableState.value.copy(
                    screen = Screen.EPISODES,
                    seasonDetails = season,
                    loading = false,
                    message = if (season.episodes.isEmpty()) "В сезоне нет эпизодов" else null,
                )
            } catch (reason: CancellationException) {
                throw reason
            } catch (reason: Exception) {
                mutableState.value = mutableState.value.copy(
                    loading = false,
                    message = reason.message ?: "Не удалось загрузить сезон",
                )
            }
        }
    }

    fun playEpisode(episode: EpisodeSummary) {
        val currentApi = api ?: return
        val selected = mutableState.value.selected ?: return
        playbackJob?.cancel()
        mutableState.value = mutableState.value.copy(
            selectedEpisode = episode,
            loading = true,
            message = null,
        )
        playbackJob = viewModelScope.launch {
            try {
                val playback = currentApi.resolveEpisode(selected.card.id, episode)
                when (playback.status) {
                    PlaybackStatus.READY -> openPlayer(playback)
                    PlaybackStatus.BUFFERING -> waitForStreamReady(currentApi, playback)
                    PlaybackStatus.SOURCE_REQUIRED,
                    PlaybackStatus.UNAVAILABLE -> loadSources(
                        currentApi,
                        selected.card.id,
                        MediaKind.SERIES,
                        episode.seasonNumber,
                    )
                }
            } catch (reason: CancellationException) {
                throw reason
            } catch (reason: Exception) {
                mutableState.value = mutableState.value.copy(
                    screen = Screen.EPISODES,
                    loading = false,
                    message = reason.message ?: "Не удалось подготовить эпизод",
                )
            }
        }
    }

    fun selectSource(source: SourceRelease) {
        val currentApi = api ?: return
        val selected = mutableState.value.selected ?: return
        playbackJob?.cancel()
        mutableState.value = mutableState.value.copy(
            screen = Screen.PREPARING,
            loading = false,
            message = "Добавляем источник в qBittorrent…",
        )
        playbackJob = viewModelScope.launch {
            try {
                val episode = mutableState.value.selectedEpisode
                if (selected.card.kind == MediaKind.SERIES && episode == null) {
                    throw IllegalStateException("Сначала выберите эпизод")
                }
                val taskId = currentApi.addSource(
                    mediaId = selected.card.id,
                    kind = selected.card.kind,
                    sourceId = source.id,
                    seasonNumber = episode?.seasonNumber,
                )
                if (episode == null) {
                    waitForPlaybackMetadata(currentApi, selected.card.id, null)
                } else {
                    prepareSeriesSource(currentApi, selected.card.id, taskId, episode)
                }
            } catch (reason: CancellationException) {
                throw reason
            } catch (reason: Exception) {
                mutableState.value = mutableState.value.copy(
                    screen = Screen.SOURCES,
                    loading = false,
                    message = reason.message ?: "Не удалось добавить источник",
                )
            }
        }
    }

    fun selectEpisodeFile(file: EpisodeMatchFile) {
        val currentApi = api ?: return
        val selected = mutableState.value.selected ?: return
        val episode = mutableState.value.selectedEpisode ?: return
        val taskId = mutableState.value.episodeMatchTaskId ?: return
        playbackJob?.cancel()
        mutableState.value = mutableState.value.copy(
            screen = Screen.PREPARING,
            message = "Сохраняем соответствие серии…",
        )
        playbackJob = viewModelScope.launch {
            try {
                val report = currentApi.confirmEpisodeMatch(taskId, file, episode)
                require(report.hasConfirmedEpisode(episode)) {
                    "Сервер не подтвердил соответствие выбранной серии"
                }
                waitForPlaybackMetadata(currentApi, selected.card.id, episode)
            } catch (reason: CancellationException) {
                throw reason
            } catch (reason: Exception) {
                mutableState.value = mutableState.value.copy(
                    screen = Screen.MATCH_FILES,
                    message = reason.message ?: "Не удалось сохранить соответствие серии",
                )
            }
        }
    }

    fun clearMessage() {
        mutableState.value = mutableState.value.copy(message = null)
    }

    fun changeServer() {
        playbackJob?.cancel()
        serverStore.clear()
        api = null
        mutableState.value = UiState(screen = Screen.SETUP)
    }

    fun navigateBack(): Boolean = when (mutableState.value.screen) {
        Screen.PLAYER -> {
            val destination = if (mutableState.value.selectedEpisode != null) Screen.EPISODES else Screen.DETAILS
            mutableState.value = mutableState.value.copy(screen = destination, playerUrl = null)
            true
        }
        Screen.EPISODES -> {
            playbackJob?.cancel()
            mutableState.value = mutableState.value.copy(
                screen = Screen.DETAILS,
                seasonDetails = null,
                selectedEpisode = null,
                message = null,
            )
            true
        }
        Screen.DETAILS -> {
            mutableState.value = mutableState.value.copy(screen = Screen.CATALOG, selected = null, message = null)
            true
        }
        Screen.SOURCES -> {
            playbackJob?.cancel()
            val destination = if (mutableState.value.selectedEpisode != null) Screen.EPISODES else Screen.DETAILS
            mutableState.value = mutableState.value.copy(
                screen = destination,
                sources = emptyList(),
                message = null,
            )
            true
        }
        Screen.MATCH_FILES -> {
            playbackJob?.cancel()
            mutableState.value = mutableState.value.copy(
                screen = Screen.SOURCES,
                episodeMatchFiles = emptyList(),
                episodeMatchTaskId = null,
                message = null,
            )
            true
        }
        Screen.PREPARING -> {
            playbackJob?.cancel()
            val destination = when {
                mutableState.value.sources.isNotEmpty() -> Screen.SOURCES
                mutableState.value.selectedEpisode != null -> Screen.EPISODES
                else -> Screen.DETAILS
            }
            mutableState.value = mutableState.value.copy(screen = destination, message = null)
            true
        }
        Screen.SETUP, Screen.CATALOG -> false
    }

    private suspend fun loadSources(
        client: KadrApi,
        mediaId: Int,
        kind: MediaKind,
        seasonNumber: Int? = null,
    ) {
        val sources = client.sources(mediaId, kind, seasonNumber)
        mutableState.value = mutableState.value.copy(
            screen = Screen.SOURCES,
            sources = sources,
            recommendedSourceId = recommendedSourceId(sources),
            loading = false,
            message = if (sources.isEmpty()) "Источники не найдены" else null,
        )
    }

    private suspend fun prepareSeriesSource(
        client: KadrApi,
        mediaId: Int,
        taskId: String,
        episode: EpisodeSummary,
    ) {
        mutableState.value = mutableState.value.copy(
            screen = Screen.PREPARING,
            message = "Получаем список файлов раздачи…",
        )
        var metadataReady = false
        for (attempt in 0 until TORRENT_FILE_ATTEMPTS) {
            if (attempt > 0) delay(TORRENT_FILE_POLL_INTERVAL_MS)
            if (client.hasVideoFiles(taskId)) {
                metadataReady = true
                break
            }
        }
        if (!metadataReady) {
            mutableState.value = mutableState.value.copy(
                screen = Screen.SOURCES,
                message = "Метаданные файлов ещё не загрузились. Повторите выбор немного позже.",
            )
            return
        }
        val report = client.analyzeEpisodeMatches(taskId)
        if (report.hasConfirmedEpisode(episode)) {
            waitForPlaybackMetadata(client, mediaId, episode)
            return
        }
        val candidates = report.files.filter { !it.confirmed && !it.unsafe }
        mutableState.value = mutableState.value.copy(
            screen = Screen.MATCH_FILES,
            episodeMatchFiles = candidates,
            episodeMatchTaskId = taskId,
            loading = false,
            message = when {
                !report.metadataAvailable -> "Метаданные эпизодов временно недоступны"
                candidates.isEmpty() -> "В источнике нет безопасного файла для выбранной серии"
                else -> null
            },
        )
    }

    private suspend fun waitForPlaybackMetadata(
        client: KadrApi,
        mediaId: Int,
        episode: EpisodeSummary?,
    ) {
        mutableState.value = mutableState.value.copy(
            screen = Screen.PREPARING,
            loading = false,
            message = "Получаем метаданные раздачи…",
        )
        repeat(METADATA_ATTEMPTS) { attempt ->
            if (attempt > 0) delay(PLAYBACK_POLL_INTERVAL_MS)
            val playback = try {
                if (episode == null) client.resolveMovie(mediaId)
                else client.resolveEpisode(mediaId, episode)
            } catch (reason: CancellationException) {
                throw reason
            } catch (reason: Exception) {
                if (attempt >= METADATA_GRACE_ATTEMPTS) throw reason
                mutableState.value = mutableState.value.copy(
                    message = "Получаем метаданные раздачи…",
                )
                null
            }
            if (playback == null) {
                return@repeat
            }
            when (playback.status) {
                PlaybackStatus.READY -> {
                    openPlayer(playback)
                    return
                }
                PlaybackStatus.BUFFERING -> {
                    waitForStreamReady(client, playback)
                    return
                }
                PlaybackStatus.SOURCE_REQUIRED -> mutableState.value = mutableState.value.copy(
                    message = "Источник добавлен, ждём метаданные раздачи…",
                )
                PlaybackStatus.UNAVAILABLE -> throw IllegalStateException(
                    playback.message ?: "Источник недоступен для воспроизведения",
                )
            }
        }
        mutableState.value = mutableState.value.copy(
            screen = Screen.SOURCES,
            message = "Метаданные раздачи не загрузились. Можно выбрать другой источник или повторить позже.",
        )
    }

    private suspend fun waitForStreamReady(client: KadrApi, playback: PlaybackResolution) {
        val taskId = playback.taskId
            ?: throw IllegalStateException("Сервер не вернул идентификатор раздачи")
        var displayedProgress = playback.bufferProgress.coerceIn(0.0, 1.0)
        mutableState.value = mutableState.value.copy(
            screen = Screen.PREPARING,
            loading = false,
            message = preparationMessage(displayedProgress, 0.0, 0),
        )
        repeat(BUFFER_ATTEMPTS) { attempt ->
            if (attempt > 0) delay(PLAYBACK_POLL_INTERVAL_MS)
            val readiness = client.streamReadiness(taskId)
            displayedProgress = monotonicBufferProgress(
                displayedProgress,
                readiness.bufferProgress,
            )
            mutableState.value = mutableState.value.copy(
                message = preparationMessage(
                    displayedProgress,
                    readiness.fileProgress,
                    readiness.downloadSpeedBytes,
                ),
            )
            if (readiness.ready) {
                openPlayer(playback)
                return
            }
        }
        mutableState.value = mutableState.value.copy(
            screen = if (mutableState.value.sources.isNotEmpty()) {
                Screen.SOURCES
            } else if (mutableState.value.selectedEpisode != null) {
                Screen.EPISODES
            } else {
                Screen.DETAILS
            },
            message = "Начальный буфер не подготовился за 10 минут. Выберите другой источник.",
        )
    }

    private fun openPlayer(playback: PlaybackResolution) {
        val url = playback.streamUrl
        mutableState.value = if (url == null) {
            mutableState.value.copy(loading = false, message = "Сервер не вернул адрес видеопотока")
        } else {
            mutableState.value.copy(
                screen = Screen.PLAYER,
                playerUrl = url,
                resumePositionMs = playback.resumePositionSeconds * 1_000,
                loading = false,
                message = null,
            )
        }
    }

    private fun preparationMessage(progress: Double, fileProgress: Double, speedBytes: Long): String {
        val bufferPercent = (progress.coerceIn(0.0, 1.0) * 100).toInt()
        val filePercent = (fileProgress.coerceIn(0.0, 1.0) * 100).toInt()
        val speed = if (speedBytes > 0) " · ${formatSpeed(speedBytes)}" else ""
        return "Начальный буфер: $bufferPercent% · файл: $filePercent%$speed"
    }

    private fun formatSpeed(bytes: Long): String {
        val mebibytes = bytes.toDouble() / (1024.0 * 1024.0)
        return "%.1f МБ/с".format(mebibytes)
    }

    private suspend fun loadCatalog(client: KadrApi): Pair<List<MediaCard>, List<MediaCard>> = coroutineScope {
        val movies = async { client.popular(MediaKind.MOVIE) }
        val series = async { client.popular(MediaKind.SERIES) }
        movies.await() to series.await()
    }

    private companion object {
        const val METADATA_ATTEMPTS = 12
        const val METADATA_GRACE_ATTEMPTS = 6
        const val BUFFER_ATTEMPTS = 120
        const val TORRENT_FILE_ATTEMPTS = 12
        const val TORRENT_FILE_POLL_INTERVAL_MS = 1_000L
        const val PLAYBACK_POLL_INTERVAL_MS = 5_000L
    }
}
