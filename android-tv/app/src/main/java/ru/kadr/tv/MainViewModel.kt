package ru.kadr.tv

import android.app.Application
import android.util.Log
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
import ru.kadr.tv.data.HistoryItem
import ru.kadr.tv.data.MediaCard
import ru.kadr.tv.data.MediaDetails
import ru.kadr.tv.data.MediaKind
import ru.kadr.tv.data.PlaybackResolution
import ru.kadr.tv.data.PlaybackStatus
import ru.kadr.tv.data.ServerAddress
import ru.kadr.tv.data.ServerStore
import ru.kadr.tv.data.SeasonDetails
import ru.kadr.tv.data.SavedLibraryItem
import ru.kadr.tv.data.SourceRelease
import ru.kadr.tv.data.monotonicBufferProgress
import ru.kadr.tv.data.normalizeSearchInput
import ru.kadr.tv.data.recommendedSourceId
import ru.kadr.tv.data.hasConfirmedEpisode
import ru.kadr.tv.data.matches
import ru.kadr.tv.data.searchableQuery
import ru.kadr.tv.data.asMediaCard

enum class Screen {
    SETUP,
    CATALOG,
    SEARCH,
    LIBRARY,
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
    val searchQuery: String = "",
    val searchMovies: List<MediaCard> = emptyList(),
    val searchSeries: List<MediaCard> = emptyList(),
    val searchLoading: Boolean = false,
    val libraryItems: List<SavedLibraryItem> = emptyList(),
    val favoriteItems: List<MediaCard> = emptyList(),
    val historyItems: List<HistoryItem> = emptyList(),
    val selected: MediaDetails? = null,
    val detailsOrigin: Screen = Screen.CATALOG,
    val selectedSeasonNumber: Int? = null,
    val seasonDetails: SeasonDetails? = null,
    val selectedEpisode: EpisodeSummary? = null,
    val sources: List<SourceRelease> = emptyList(),
    val recommendedSourceId: String? = null,
    val episodeMatchFiles: List<EpisodeMatchFile> = emptyList(),
    val episodeMatchTaskId: String? = null,
    val playerUrl: String? = null,
    val resumePositionMs: Long = 0,
    val playerMedia: MediaCard? = null,
    val playerEpisode: EpisodeSummary? = null,
    val playerReturnScreen: Screen = Screen.DETAILS,
    val loading: Boolean = false,
    val message: String? = null,
)

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val serverStore = ServerStore(application)
    private var api: KadrApi? = null
    private var playbackJob: Job? = null
    private var searchJob: Job? = null
    private var historyJob: Job? = null
    private var libraryJob: Job? = null
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
        val origin = when (mutableState.value.screen) {
            Screen.SEARCH -> Screen.SEARCH
            Screen.LIBRARY -> Screen.LIBRARY
            else -> Screen.CATALOG
        }
        mutableState.value = mutableState.value.copy(loading = true, message = null)
        viewModelScope.launch {
            runCatching { currentApi.details(media.kind, media.id) }
                .onSuccess { details ->
                    mutableState.value = mutableState.value.copy(
                        screen = Screen.DETAILS,
                        selected = details,
                        detailsOrigin = origin,
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

    fun openSearch() {
        mutableState.value = mutableState.value.copy(screen = Screen.SEARCH, message = null)
    }

    fun openLibrary() {
        val currentApi = api ?: return
        libraryJob?.cancel()
        mutableState.value = mutableState.value.copy(
            screen = Screen.LIBRARY,
            loading = true,
            message = null,
        )
        libraryJob = viewModelScope.launch {
            try {
                val (libraryAndFavorites, history) = coroutineScope {
                    val saved = async { currentApi.library() }
                    val favorites = async { currentApi.favorites() }
                    val watched = async { currentApi.history() }
                    (saved.await() to favorites.await()) to watched.await()
                }
                mutableState.value = mutableState.value.copy(
                    screen = Screen.LIBRARY,
                    libraryItems = libraryAndFavorites.first,
                    favoriteItems = libraryAndFavorites.second,
                    historyItems = history.filter { !it.completed && it.positionSeconds > 0 },
                    loading = false,
                    message = null,
                )
            } catch (reason: CancellationException) {
                throw reason
            } catch (reason: Exception) {
                mutableState.value = mutableState.value.copy(
                    screen = Screen.LIBRARY,
                    loading = false,
                    message = reason.message ?: "Не удалось загрузить библиотеку",
                )
            }
        }
    }

    fun retryLibrary() = openLibrary()

    fun openLibraryItem(item: SavedLibraryItem) {
        val history = mutableState.value.historyItems.firstOrNull { it.matches(item) }
        val episode = item.episodeNumber?.let { number ->
            EpisodeSummary(
                id = item.catalogEpisodeId ?: 0,
                seasonNumber = item.seasonNumber ?: 0,
                number = number,
                name = "Серия $number",
                overview = "",
                runtimeMinutes = null,
                rating = 0.0,
                stillUrl = null,
            )
        }
        mutableState.value = mutableState.value.copy(
            screen = Screen.PLAYER,
            playerUrl = item.streamUrl,
            resumePositionMs = (history?.positionSeconds ?: 0) * 1_000,
            playerMedia = item.asMediaCard(),
            playerEpisode = episode,
            playerReturnScreen = Screen.LIBRARY,
            message = null,
        )
    }

    fun openHistoryItem(item: HistoryItem) {
        val currentApi = api ?: return
        libraryJob?.cancel()
        mutableState.value = mutableState.value.copy(loading = true, message = null)
        libraryJob = viewModelScope.launch {
            try {
                val details = currentApi.details(item.mediaKind, item.mediaId)
                if (item.mediaKind == MediaKind.MOVIE) {
                    mutableState.value = mutableState.value.copy(
                        screen = Screen.DETAILS,
                        selected = details,
                        detailsOrigin = Screen.LIBRARY,
                        selectedSeasonNumber = null,
                        seasonDetails = null,
                        selectedEpisode = null,
                        loading = false,
                    )
                    playSelected()
                    return@launch
                }
                val seasonNumber = requireNotNull(item.seasonNumber) {
                    "В истории не указан сезон"
                }
                val episodeNumber = requireNotNull(item.episodeNumber) {
                    "В истории не указана серия"
                }
                val season = currentApi.season(item.mediaId, seasonNumber)
                val episode = season.episodes.firstOrNull { candidate ->
                    candidate.number == episodeNumber ||
                        item.catalogEpisodeId != null && candidate.id == item.catalogEpisodeId
                } ?: error("Серия из истории больше не найдена в каталоге")
                mutableState.value = mutableState.value.copy(
                    screen = Screen.EPISODES,
                    selected = details,
                    detailsOrigin = Screen.LIBRARY,
                    selectedSeasonNumber = seasonNumber,
                    seasonDetails = season,
                    selectedEpisode = episode,
                    loading = false,
                )
                playEpisode(episode)
            } catch (reason: CancellationException) {
                throw reason
            } catch (reason: Exception) {
                mutableState.value = mutableState.value.copy(
                    screen = Screen.LIBRARY,
                    loading = false,
                    message = reason.message ?: "Не удалось продолжить просмотр",
                )
            }
        }
    }

    fun updateSearchQuery(query: String) {
        searchJob?.cancel()
        val normalized = normalizeSearchInput(query)
        val searchable = searchableQuery(normalized)
        mutableState.value = mutableState.value.copy(
            searchQuery = normalized,
            searchLoading = searchable != null,
            message = null,
            searchMovies = if (searchable != null) {
                mutableState.value.searchMovies
            } else {
                emptyList()
            },
            searchSeries = if (searchable != null) {
                mutableState.value.searchSeries
            } else {
                emptyList()
            },
        )
        if (searchable == null) return
        searchJob = viewModelScope.launch {
            delay(SEARCH_DEBOUNCE_MS)
            performSearch(searchable)
        }
    }

    fun submitSearch() {
        val query = searchableQuery(mutableState.value.searchQuery) ?: return
        searchJob?.cancel()
        mutableState.value = mutableState.value.copy(searchLoading = true, message = null)
        searchJob = viewModelScope.launch { performSearch(query) }
    }

    fun retrySearch() = submitSearch()

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

    fun reportPlaybackProgress(positionMs: Long, durationMs: Long, completed: Boolean, final: Boolean) {
        val currentApi = api ?: return
        val media = mutableState.value.playerMedia ?: return
        val episode = mutableState.value.playerEpisode
        val previousUpdate = historyJob
        if (!final && previousUpdate?.isActive == true) return
        historyJob = viewModelScope.launch {
            if (final) previousUpdate?.join()
            try {
                currentApi.updateHistory(
                    media = media,
                    episode = episode,
                    positionSeconds = if (completed) 0 else positionMs.coerceAtLeast(0) / 1_000,
                    durationSeconds = durationMs.coerceAtLeast(0) / 1_000,
                    completed = completed,
                )
            } catch (reason: CancellationException) {
                throw reason
            } catch (reason: Exception) {
                Log.w(LOG_TAG, "watch_history_update_failed", reason)
            }
        }
    }

    fun changeServer() {
        playbackJob?.cancel()
        searchJob?.cancel()
        historyJob?.cancel()
        libraryJob?.cancel()
        serverStore.clear()
        api = null
        mutableState.value = UiState(screen = Screen.SETUP)
    }

    fun navigateBack(): Boolean = when (mutableState.value.screen) {
        Screen.PLAYER -> {
            mutableState.value = mutableState.value.copy(
                screen = mutableState.value.playerReturnScreen,
                playerUrl = null,
            )
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
            mutableState.value = mutableState.value.copy(
                screen = mutableState.value.detailsOrigin,
                selected = null,
                message = null,
            )
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
        Screen.SEARCH -> {
            searchJob?.cancel()
            mutableState.value = mutableState.value.copy(
                screen = Screen.CATALOG,
                searchLoading = false,
                message = null,
            )
            true
        }
        Screen.LIBRARY -> {
            libraryJob?.cancel()
            mutableState.value = mutableState.value.copy(screen = Screen.CATALOG, message = null)
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
                playerMedia = mutableState.value.selected?.card,
                playerEpisode = mutableState.value.selectedEpisode,
                playerReturnScreen = if (mutableState.value.selectedEpisode != null) {
                    Screen.EPISODES
                } else {
                    Screen.DETAILS
                },
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

    private suspend fun performSearch(query: String) {
        val currentApi = api ?: return
        try {
            val (movies, series) = coroutineScope {
                val movieRequest = async { currentApi.search(MediaKind.MOVIE, query) }
                val seriesRequest = async { currentApi.search(MediaKind.SERIES, query) }
                movieRequest.await() to seriesRequest.await()
            }
            if (mutableState.value.searchQuery.trim() != query) return
            mutableState.value = mutableState.value.copy(
                searchMovies = movies,
                searchSeries = series,
                searchLoading = false,
                message = if (movies.isEmpty() && series.isEmpty()) {
                    "По запросу «$query» ничего не найдено"
                } else {
                    null
                },
            )
        } catch (reason: CancellationException) {
            throw reason
        } catch (reason: Exception) {
            mutableState.value = mutableState.value.copy(
                searchLoading = false,
                message = reason.message ?: "Не удалось выполнить поиск",
            )
        }
    }

    private companion object {
        const val LOG_TAG = "KadrTv"
        const val METADATA_ATTEMPTS = 12
        const val METADATA_GRACE_ATTEMPTS = 6
        const val BUFFER_ATTEMPTS = 120
        const val TORRENT_FILE_ATTEMPTS = 12
        const val TORRENT_FILE_POLL_INTERVAL_MS = 1_000L
        const val PLAYBACK_POLL_INTERVAL_MS = 5_000L
        const val SEARCH_DEBOUNCE_MS = 600L
    }
}
