package ru.kadr.tv.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusGroup
import androidx.compose.foundation.focusable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.focusProperties
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.tv.material3.Button
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import kotlinx.coroutines.delay
import ru.kadr.tv.MainViewModel
import ru.kadr.tv.Screen
import ru.kadr.tv.UiState
import ru.kadr.tv.data.MediaCard
import ru.kadr.tv.data.MediaDetails
import ru.kadr.tv.data.EpisodeMatchFile
import ru.kadr.tv.data.EpisodeSummary
import ru.kadr.tv.data.SourceRelease

private val Background = Color(0xFF101116)
private val Surface = Color(0xFF20222B)
private val Accent = Color(0xFF8B5CF6)
private val SecondaryText = Color(0xFFA1A1AA)

@Composable
fun KadrTvApp(viewModel: MainViewModel) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    BackHandler(
        enabled = state.screen == Screen.SEARCH ||
            state.screen == Screen.DETAILS ||
            state.screen == Screen.EPISODES ||
            state.screen == Screen.SOURCES ||
            state.screen == Screen.MATCH_FILES ||
            state.screen == Screen.PREPARING ||
            state.screen == Screen.PLAYER,
    ) {
        viewModel.navigateBack()
    }
    MaterialTheme {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Background),
        ) {
            when (state.screen) {
                Screen.SETUP -> SetupScreen(state, viewModel::connect)
                Screen.CATALOG -> CatalogScreen(
                    state = state,
                    onOpen = viewModel::openMedia,
                    onRetry = viewModel::retryCatalog,
                    onSearch = viewModel::openSearch,
                    onChangeServer = viewModel::changeServer,
                )
                Screen.SEARCH -> SearchScreen(
                    state = state,
                    onQuery = viewModel::updateSearchQuery,
                    onSubmit = viewModel::submitSearch,
                    onRetry = viewModel::retrySearch,
                    onOpen = viewModel::openMedia,
                )
                Screen.DETAILS -> state.selected?.let { details ->
                    DetailsScreen(details, state, viewModel::playSelected, viewModel::clearMessage)
                }
                Screen.EPISODES -> EpisodeScreen(
                    state = state,
                    onSeason = viewModel::selectSeason,
                    onEpisode = viewModel::playEpisode,
                )
                Screen.SOURCES -> SourceScreen(state, viewModel::selectSource)
                Screen.MATCH_FILES -> MatchFilesScreen(state, viewModel::selectEpisodeFile)
                Screen.PREPARING -> PreparingScreen(state)
                Screen.PLAYER -> state.playerUrl?.let { url ->
                    PlayerScreen(url, state.resumePositionMs)
                }
            }
            if (state.loading) LoadingOverlay()
        }
    }
}

@Composable
private fun EpisodeScreen(
    state: UiState,
    onSeason: (Int) -> Unit,
    onEpisode: (EpisodeSummary) -> Unit,
) {
    val selectedSeasonFocus = remember { FocusRequester() }
    val firstEpisodeFocus = remember { FocusRequester() }
    LaunchedEffect(state.selectedSeasonNumber, state.seasonDetails) {
        delay(200)
        runCatching { selectedSeasonFocus.requestFocus() }
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 42.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item(key = "episode-header") {
            Column(modifier = Modifier.padding(horizontal = 64.dp)) {
                Text(
                    state.selected?.card?.title.orEmpty(),
                    color = Color.White,
                    fontSize = 38.sp,
                    fontWeight = FontWeight.Black,
                )
                Text("Выберите сезон и серию", color = SecondaryText, fontSize = 18.sp)
            }
        }
        item(key = "seasons") {
            LazyRow(
                modifier = Modifier.padding(top = 8.dp).focusGroup(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 64.dp),
            ) {
                items(state.selected?.seasons.orEmpty(), key = { it.id }) { season ->
                    Button(
                        onClick = { onSeason(season.number) },
                        modifier = Modifier
                            .focusProperties { down = firstEpisodeFocus }
                            .then(
                                if (season.number == state.selectedSeasonNumber) {
                                    Modifier.focusRequester(selectedSeasonFocus)
                                } else {
                                    Modifier
                                },
                            ),
                    ) {
                        Text("${season.name} · ${season.episodeCount}")
                    }
                }
            }
        }
        state.seasonDetails?.let { season ->
            item(key = "season-title") {
                Column(modifier = Modifier.padding(horizontal = 64.dp, vertical = 8.dp)) {
                    Text(season.name, color = Color.White, fontSize = 26.sp, fontWeight = FontWeight.Bold)
                    if (season.overview.isNotBlank()) {
                        Text(
                            season.overview,
                            color = SecondaryText,
                            fontSize = 16.sp,
                            maxLines = 3,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.padding(top = 6.dp),
                        )
                    }
                }
            }
            itemsIndexed(season.episodes, key = { _, episode -> episode.id }) { index, episode ->
                EpisodeTile(
                    episode = episode,
                    onEpisode = onEpisode,
                    focusRequester = firstEpisodeFocus.takeIf { index == 0 },
                    upFocus = selectedSeasonFocus,
                )
            }
        }
        state.message?.let { message ->
            item(key = "episode-message") {
                Text(
                    message,
                    color = Color(0xFFFCA5A5),
                    fontSize = 18.sp,
                    modifier = Modifier.padding(horizontal = 64.dp, vertical = 8.dp),
                )
            }
        }
    }
}

@Composable
private fun EpisodeTile(
    episode: EpisodeSummary,
    onEpisode: (EpisodeSummary) -> Unit,
    focusRequester: FocusRequester?,
    upFocus: FocusRequester,
) {
    Button(
        onClick = { onEpisode(episode) },
        modifier = Modifier
            .padding(horizontal = 64.dp)
            .fillMaxWidth()
            .focusProperties { up = upFocus }
            .then(if (focusRequester != null) Modifier.focusRequester(focusRequester) else Modifier),
    ) {
        Row(modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp)) {
            Text(
                episode.number.toString().padStart(2, '0'),
                fontSize = 22.sp,
                fontWeight = FontWeight.Black,
                modifier = Modifier.width(54.dp),
            )
            Column(modifier = Modifier.weight(1f)) {
                Text(episode.name.ifBlank { "Серия ${episode.number}" }, fontSize = 19.sp, fontWeight = FontWeight.Bold)
                Text(
                    listOfNotNull(
                        episode.runtimeMinutes?.let { "$it мин" },
                        "★ ${"%.1f".format(episode.rating)}".takeIf { episode.rating > 0 },
                    ).joinToString(" · "),
                    fontSize = 14.sp,
                    modifier = Modifier.padding(top = 3.dp),
                )
            }
        }
    }
}

@Composable
private fun MatchFilesScreen(state: UiState, onSelect: (EpisodeMatchFile) -> Unit) {
    val episode = state.selectedEpisode
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 72.dp, vertical = 48.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item(key = "match-header") {
            Column(modifier = Modifier.padding(bottom = 12.dp)) {
                Text("Какой файл содержит серию?", color = Color.White, fontSize = 36.sp, fontWeight = FontWeight.Black)
                Text(
                    "S${episode?.seasonNumber ?: 0}E${episode?.number ?: 0} · ${episode?.name.orEmpty()}",
                    color = SecondaryText,
                    fontSize = 20.sp,
                    modifier = Modifier.padding(top = 6.dp),
                )
                Text(
                    "Автоматическое сопоставление не было однозначным. Выберите файл вручную.",
                    color = SecondaryText,
                    fontSize = 16.sp,
                    modifier = Modifier.padding(top = 12.dp),
                )
            }
        }
        items(state.episodeMatchFiles, key = { it.fileId }) { file ->
            Button(onClick = { onSelect(file) }, modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp)) {
                    Text(file.filePath, fontSize = 17.sp, fontWeight = FontWeight.Bold)
                    val hints = (file.episodes + file.alternatives).distinctBy {
                        it.seasonNumber to it.episodeNumber
                    }.joinToString { "S${it.seasonNumber}E${it.episodeNumber}" }
                    if (hints.isNotBlank()) {
                        Text("Распознано: $hints", fontSize = 14.sp, modifier = Modifier.padding(top = 4.dp))
                    }
                }
            }
        }
        state.message?.let { message ->
            item(key = "match-message") {
                Text(message, color = Color(0xFFFCA5A5), fontSize = 18.sp)
            }
        }
    }
}

@Composable
private fun SourceScreen(state: UiState, onSelect: (SourceRelease) -> Unit) {
    val episode = state.selectedEpisode
    val title = buildString {
        append(state.selected?.card?.title.orEmpty())
        if (episode != null) append(" · S${episode.seasonNumber}E${episode.number}")
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(
            horizontal = 72.dp,
            vertical = 48.dp,
        ),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item(key = "header") {
            Column(modifier = Modifier.padding(bottom = 14.dp)) {
                Text("Выберите источник", color = Color.White, fontSize = 38.sp, fontWeight = FontWeight.Black)
                Text(title, color = SecondaryText, fontSize = 20.sp, modifier = Modifier.padding(top = 6.dp))
                Text(
                    "Источники отсортированы по числу раздающих. Нажмите OK, чтобы начать подготовку фильма.",
                    color = SecondaryText,
                    fontSize = 16.sp,
                    modifier = Modifier.padding(top = 12.dp),
                )
            }
        }
        items(state.sources, key = { it.id }) { source ->
            SourceTile(
                source = source,
                recommended = source.id == state.recommendedSourceId,
                onSelect = onSelect,
            )
        }
        state.message?.let { message ->
            item(key = "message") {
                Text(
                    message,
                    color = Color(0xFFFCA5A5),
                    fontSize = 18.sp,
                    modifier = Modifier.padding(top = 12.dp),
                )
            }
        }
    }
}

@Composable
private fun SourceTile(source: SourceRelease, recommended: Boolean, onSelect: (SourceRelease) -> Unit) {
    Button(
        onClick = { onSelect(source) },
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    listOfNotNull(
                        source.resolution,
                        source.source,
                        source.codec,
                        "HDR".takeIf { source.hdr },
                        source.language,
                    ).ifEmpty { listOf("Источник") }.joinToString(" · "),
                    fontSize = 19.sp,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    "${formatSize(source.sizeBytes)}  ·  раздают: ${source.seeders ?: "—"}",
                    fontSize = 15.sp,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
            if (recommended) {
                Text("РЕКОМЕНДУЕМ", fontSize = 13.sp, fontWeight = FontWeight.Black)
            }
        }
    }
}

@Composable
private fun PreparingScreen(state: UiState) {
    Column(
        modifier = Modifier.fillMaxSize().padding(horizontal = 96.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Подготовка фильма", color = Color.White, fontSize = 40.sp, fontWeight = FontWeight.Black)
        Text(
            state.selected?.card?.title.orEmpty(),
            color = SecondaryText,
            fontSize = 22.sp,
            modifier = Modifier.padding(top = 10.dp),
        )
        Box(Modifier.padding(top = 32.dp).size(22.dp).background(Accent, RoundedCornerShape(99.dp)))
        Text(
            state.message ?: "Подключаем источник…",
            color = Color.White,
            fontSize = 21.sp,
            modifier = Modifier.padding(top = 22.dp),
        )
        Text(
            "Можно нажать Назад и выбрать другой источник.",
            color = SecondaryText,
            fontSize = 15.sp,
            modifier = Modifier.padding(top = 14.dp),
        )
    }
}

private fun formatSize(bytes: Long): String {
    val gib = bytes.toDouble() / (1024.0 * 1024.0 * 1024.0)
    return if (gib >= 1.0) "%.1f ГБ".format(gib) else "%.0f МБ".format(bytes / (1024.0 * 1024.0))
}

@Composable
private fun SetupScreen(state: UiState, onConnect: (String) -> Unit) {
    var address by remember(state.serverUrl) { mutableStateOf(state.serverUrl ?: "http://192.168.1.50:8180") }
    val fieldFocus = remember { FocusRequester() }
    LaunchedEffect(fieldFocus) {
        delay(250)
        fieldFocus.requestFocus()
    }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 96.dp, vertical = 64.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("KADR", color = Color.White, fontSize = 48.sp, fontWeight = FontWeight.Black)
        Text(
            "Подключение Android TV",
            color = Color.White,
            fontSize = 28.sp,
            modifier = Modifier.padding(top = 12.dp),
        )
        Text(
            "Введите адрес KADR в локальной сети или адрес Tailscale. Например: " +
                "http://192.168.1.50:8180 или http://100.64.0.10:8180",
            color = SecondaryText,
            fontSize = 18.sp,
            modifier = Modifier.padding(top = 14.dp).width(820.dp),
        )
        BasicTextField(
            value = address,
            onValueChange = { address = it },
            singleLine = true,
            textStyle = TextStyle(color = Color.White, fontSize = 22.sp),
            modifier = Modifier
                .padding(top = 28.dp)
                .width(760.dp)
                .background(Surface, RoundedCornerShape(12.dp))
                .border(2.dp, Accent, RoundedCornerShape(12.dp))
                .padding(horizontal = 20.dp, vertical = 18.dp)
                .focusRequester(fieldFocus),
        )
        Row(
            modifier = Modifier.padding(top = 24.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Button(onClick = { onConnect(address) }) {
                Text("Проверить и сохранить")
            }
            Text(
                "HTTP используйте только внутри доверенной LAN или Tailscale VPN.",
                color = SecondaryText,
                fontSize = 15.sp,
                modifier = Modifier.padding(start = 24.dp),
            )
        }
        AnimatedVisibility(visible = state.message != null) {
            Text(
                state.message.orEmpty(),
                color = Color(0xFFFCA5A5),
                fontSize = 18.sp,
                modifier = Modifier.padding(top = 22.dp),
            )
        }
    }
}

@Composable
private fun SearchScreen(
    state: UiState,
    onQuery: (String) -> Unit,
    onSubmit: () -> Unit,
    onRetry: () -> Unit,
    onOpen: (MediaCard) -> Unit,
) {
    val fieldFocus = remember { FocusRequester() }
    val firstMovieFocus = remember { FocusRequester() }
    val firstSeriesFocus = remember { FocusRequester() }
    val keyboard = LocalSoftwareKeyboardController.current
    val resultsFocus = when {
        state.searchMovies.isNotEmpty() -> firstMovieFocus
        state.searchSeries.isNotEmpty() -> firstSeriesFocus
        else -> FocusRequester.Default
    }
    LaunchedEffect(Unit) {
        delay(250)
        runCatching { fieldFocus.requestFocus() }
        keyboard?.show()
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 40.dp),
    ) {
        item(key = "search-header") {
            Column(modifier = Modifier.padding(horizontal = 64.dp)) {
                Text("Поиск", color = Color.White, fontSize = 38.sp, fontWeight = FontWeight.Black)
                Text(
                    "Введите название фильма или сериала",
                    color = SecondaryText,
                    fontSize = 17.sp,
                    modifier = Modifier.padding(top = 6.dp),
                )
                Row(
                    modifier = Modifier.padding(top = 22.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    BasicTextField(
                        value = state.searchQuery,
                        onValueChange = onQuery,
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                        keyboardActions = KeyboardActions(onSearch = { onSubmit() }),
                        textStyle = TextStyle(color = Color.White, fontSize = 22.sp),
                        modifier = Modifier
                            .width(720.dp)
                            .background(Surface, RoundedCornerShape(12.dp))
                            .border(2.dp, Accent, RoundedCornerShape(12.dp))
                            .padding(horizontal = 20.dp, vertical = 17.dp)
                            .focusProperties { down = resultsFocus }
                            .focusRequester(fieldFocus),
                        decorationBox = { inner ->
                            Box {
                                if (state.searchQuery.isBlank()) {
                                    Text("Например: Интерстеллар", color = SecondaryText, fontSize = 22.sp)
                                }
                                inner()
                            }
                        },
                    )
                    Button(onClick = onSubmit, modifier = Modifier.padding(start = 16.dp)) {
                        Text("Искать")
                    }
                }
                if (state.searchLoading) {
                    Text(
                        "Ищем…",
                        color = SecondaryText,
                        fontSize = 16.sp,
                        modifier = Modifier.padding(top = 14.dp),
                    )
                }
            }
        }
        if (state.searchMovies.isNotEmpty()) {
            item(key = "search-movies") {
                MediaRail(
                    title = "Фильмы",
                    items = state.searchMovies,
                    onOpen = onOpen,
                    firstItemFocus = firstMovieFocus,
                    upFocus = fieldFocus,
                    downFocus = firstSeriesFocus.takeIf { state.searchSeries.isNotEmpty() },
                )
            }
        }
        if (state.searchSeries.isNotEmpty()) {
            item(key = "search-series") {
                MediaRail(
                    title = "Сериалы",
                    items = state.searchSeries,
                    onOpen = onOpen,
                    firstItemFocus = firstSeriesFocus,
                    upFocus = if (state.searchMovies.isNotEmpty()) firstMovieFocus else fieldFocus,
                )
            }
        }
        state.message?.let { message ->
            item(key = "search-message") {
                Row(
                    modifier = Modifier.padding(horizontal = 64.dp, vertical = 22.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(message, color = Color(0xFFFCA5A5), fontSize = 18.sp)
                    if (state.searchQuery.trim().length >= 2 && state.searchMovies.isEmpty() && state.searchSeries.isEmpty()) {
                        Button(onClick = onRetry, modifier = Modifier.padding(start = 20.dp)) {
                            Text("Повторить")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun CatalogScreen(
    state: UiState,
    onOpen: (MediaCard) -> Unit,
    onRetry: () -> Unit,
    onSearch: () -> Unit,
    onChangeServer: () -> Unit,
) {
    val firstMovieFocus = remember { FocusRequester() }
    val firstSeriesFocus = remember { FocusRequester() }
    LaunchedEffect(state.movies, state.series) {
        delay(250)
        runCatching {
            if (state.movies.isNotEmpty()) firstMovieFocus.requestFocus()
            else if (state.series.isNotEmpty()) firstSeriesFocus.requestFocus()
        }
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 36.dp),
    ) {
        item(key = "header") {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 56.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("KADR", color = Color.White, fontSize = 32.sp, fontWeight = FontWeight.Black)
                Spacer(Modifier.weight(1f))
                Text(state.serverUrl.orEmpty(), color = SecondaryText, fontSize = 14.sp)
                Button(onClick = onSearch, modifier = Modifier.padding(start = 20.dp)) {
                    Text("Поиск")
                }
                Button(onClick = onChangeServer, modifier = Modifier.padding(start = 20.dp)) {
                    Text("Сменить сервер")
                }
            }
        }
        if (state.movies.isNotEmpty()) {
            item(key = "movies") {
                MediaRail(
                    title = "Популярные фильмы",
                    items = state.movies,
                    onOpen = onOpen,
                    firstItemFocus = firstMovieFocus,
                    downFocus = firstSeriesFocus.takeIf { state.series.isNotEmpty() },
                )
            }
        }
        if (state.series.isNotEmpty()) {
            item(key = "series") {
                MediaRail(
                    title = "Популярные сериалы",
                    items = state.series,
                    onOpen = onOpen,
                    firstItemFocus = firstSeriesFocus,
                    upFocus = firstMovieFocus.takeIf { state.movies.isNotEmpty() },
                )
            }
        }
        if (state.message != null) {
            item(key = "error") {
                Row(modifier = Modifier.padding(horizontal = 56.dp, vertical = 20.dp)) {
                    Text(state.message, color = Color(0xFFFCA5A5), fontSize = 18.sp)
                    Button(onClick = onRetry, modifier = Modifier.padding(start = 24.dp)) {
                        Text("Повторить")
                    }
                }
            }
        }
    }
}

@Composable
private fun MediaRail(
    title: String,
    items: List<MediaCard>,
    onOpen: (MediaCard) -> Unit,
    firstItemFocus: FocusRequester,
    upFocus: FocusRequester? = null,
    downFocus: FocusRequester? = null,
) {
    Column(modifier = Modifier.padding(top = 28.dp)) {
        Text(
            title,
            color = Color.White,
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(horizontal = 56.dp, vertical = 10.dp),
        )
        LazyRow(
            modifier = Modifier.focusGroup(),
            horizontalArrangement = Arrangement.spacedBy(20.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 56.dp, vertical = 12.dp),
        ) {
            itemsIndexed(items, key = { _, item -> "${item.kind}-${item.id}" }) { index, media ->
                MediaTile(
                    media = media,
                    onOpen = onOpen,
                    focusRequester = firstItemFocus.takeIf { index == 0 },
                    upFocus = upFocus,
                    downFocus = downFocus,
                )
            }
        }
    }
}

@Composable
private fun MediaTile(
    media: MediaCard,
    onOpen: (MediaCard) -> Unit,
    focusRequester: FocusRequester?,
    upFocus: FocusRequester?,
    downFocus: FocusRequester?,
) {
    val interaction = remember { MutableInteractionSource() }
    val focused by interaction.collectIsFocusedAsState()
    Column(
        modifier = Modifier
            .width(210.dp)
            .scale(if (focused) 1.07f else 1f)
            .border(if (focused) 4.dp else 1.dp, if (focused) Color.White else Color(0xFF30323D), RoundedCornerShape(14.dp))
            .background(Surface, RoundedCornerShape(14.dp))
            .clickable(interactionSource = interaction, indication = null) { onOpen(media) }
            .focusProperties {
                if (upFocus != null) up = upFocus
                if (downFocus != null) down = downFocus
            }
            .then(if (focusRequester != null) Modifier.focusRequester(focusRequester) else Modifier)
            .focusable(interactionSource = interaction)
            .padding(18.dp),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(140.dp)
                .background(
                    Brush.linearGradient(listOf(Accent, Color(0xFF281B43), Background)),
                    RoundedCornerShape(10.dp),
                ),
            contentAlignment = Alignment.Center,
        ) {
            Text(media.title.take(1), color = Color.White, fontSize = 52.sp, fontWeight = FontWeight.Black)
        }
        Text(
            media.title,
            color = Color.White,
            fontSize = 18.sp,
            fontWeight = FontWeight.Bold,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(top = 14.dp),
        )
        Text(
            "${media.year ?: "—"}  ★ ${"%.1f".format(media.rating)}",
            color = SecondaryText,
            fontSize = 14.sp,
            modifier = Modifier.padding(top = 6.dp),
        )
    }
}

@Composable
private fun DetailsScreen(
    details: MediaDetails,
    state: UiState,
    onPlay: () -> Unit,
    onDismissMessage: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Brush.horizontalGradient(listOf(Color(0xFF281B43), Background)))
            .padding(horizontal = 80.dp, vertical = 64.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text(
            if (details.card.kind == ru.kadr.tv.data.MediaKind.MOVIE) "ФИЛЬМ" else "СЕРИАЛ",
            color = Color(0xFFC4B5FD),
            fontSize = 16.sp,
            fontWeight = FontWeight.Bold,
        )
        Text(
            details.card.title,
            color = Color.White,
            fontSize = 54.sp,
            fontWeight = FontWeight.Black,
            modifier = Modifier.padding(top = 12.dp).width(920.dp),
        )
        if (details.originalTitle.isNotBlank() && details.originalTitle != details.card.title) {
            Text(details.originalTitle, color = SecondaryText, fontSize = 20.sp)
        }
        Text(
            listOfNotNull(
                details.card.year?.toString(),
                details.runtimeMinutes?.let { "$it мин" },
                details.genres.take(3).joinToString(" · ").takeIf { it.isNotBlank() },
                "★ ${"%.1f".format(details.card.rating)}",
            ).joinToString("   "),
            color = Color.White,
            fontSize = 18.sp,
            modifier = Modifier.padding(top = 18.dp),
        )
        Text(
            details.card.overview.ifBlank { "Описание отсутствует" },
            color = Color(0xFFD4D4D8),
            fontSize = 20.sp,
            lineHeight = 29.sp,
            maxLines = 6,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(top = 22.dp).width(900.dp),
        )
        Button(onClick = onPlay, modifier = Modifier.padding(top = 30.dp)) {
            Text(if (details.card.kind == ru.kadr.tv.data.MediaKind.MOVIE) "Смотреть" else "Выбрать эпизод")
        }
        if (state.message != null) {
            Row(
                modifier = Modifier
                    .padding(top = 24.dp)
                    .background(Color(0xFF381B27), RoundedCornerShape(10.dp))
                    .padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(state.message, color = Color(0xFFFCA5A5), fontSize = 17.sp)
                Button(onClick = onDismissMessage, modifier = Modifier.padding(start = 20.dp)) {
                    Text("Закрыть")
                }
            }
        }
    }
}

@Composable
private fun LoadingOverlay() {
    Box(
        modifier = Modifier.fillMaxSize().background(Color(0xB0000000)),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Box(Modifier.size(18.dp).background(Accent, RoundedCornerShape(99.dp)))
            Text("Загрузка…", color = Color.White, fontSize = 22.sp, modifier = Modifier.padding(top = 18.dp))
        }
    }
}
