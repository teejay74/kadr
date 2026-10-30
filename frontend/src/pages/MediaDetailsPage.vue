<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import CastCarousel from '../components/CastCarousel.vue'
import EpisodeMatchDialog from '../components/EpisodeMatchDialog.vue'
import EpisodeList from '../components/EpisodeList.vue'
import KadrPlayer from '../components/KadrPlayer.vue'
import MediaActions from '../components/MediaActions.vue'
import MediaHero from '../components/MediaHero.vue'
import NextEpisodeOverlay from '../components/NextEpisodeOverlay.vue'
import SeasonSelector from '../components/SeasonSelector.vue'
import StatePanel from '../components/StatePanel.vue'
import SourceSelector from '../components/SourceSelector.vue'
import {
  addTorrent,
  addFavorite,
  analyzeEpisodeMatches,
  configureTorrentPrefetch,
  confirmEpisodeMatches,
  deleteFavorite,
  friendlyApiError,
  getFavorites,
  getMediaDetails,
  getSeriesSeason,
  getSources,
  getTorrentFiles,
  prefetchNextEpisode,
  resolvePlayback,
  resolveNextEpisode,
  selectTorrentFile,
} from '../services/api'
import type {
  EpisodeMatchReport,
  EpisodeMatchSelection,
  EpisodeSummary,
  MediaDetails,
  MediaKind,
  NextEpisodeResolution,
  PlaybackResolution,
  SeasonDetails,
  SeasonSummary,
  SourceRelease,
} from '../types/media'

const route = useRoute()
const kind = computed(() => route.meta.kind as MediaKind)
const media = ref<MediaDetails | null>(null)
const loading = ref(true)
const error = ref('')
const favorite = ref(false)
const favoriteBusy = ref(false)
const selectedSeasonNumber = ref(0)
const seasonDetails = ref<SeasonDetails | null>(null)
const seasonLoading = ref(false)
const seasonError = ref('')
const selectedEpisode = ref<EpisodeSummary | null>(null)
const playback = ref<PlaybackResolution | null>(null)
const playbackLoading = ref(false)
const playbackMessage = ref('')
const sourceSelectorOpen = ref(false)
const sourceIntent = ref<'playback' | 'season'>('playback')
const sourceSelectorLoading = ref(false)
const sourceSelectorError = ref('')
const sourceItems = ref<SourceRelease[]>([])
const sourceBusyId = ref<string | null>(null)
const sourceTaskId = ref<string | null>(null)
const sourceMatchReport = ref<EpisodeMatchReport | null>(null)
const sourceMatchOpen = ref(false)
const seasonDownloadMessage = ref('')
const nextEpisodeResult = ref<NextEpisodeResolution | null>(null)
const nextEpisodeLoading = ref(false)
const nextEpisodeOpen = ref(false)
const nextPrefetchStarted = ref(false)
const autoNext = ref(readAutoNext())
let seasonRequestId = 0

const availableSeasons = computed<SeasonSummary[]>(() => {
  const seasons = media.value?.seasons ?? []
  const regular = seasons.filter((season) => season.number > 0)
  return regular.length ? regular : seasons
})
const seasonStorageKey = computed(() => `kadr:season:${media.value?.id ?? 'unknown'}`)

function readStoredSeason(): number | null {
  try {
    const value = Number(localStorage.getItem(seasonStorageKey.value))
    return Number.isInteger(value) ? value : null
  } catch {
    return null
  }
}

function initialSeason(): number {
  const stored = readStoredSeason()
  if (stored !== null && availableSeasons.value.some((season) => season.number === stored)) {
    return stored
  }
  return availableSeasons.value[0]?.number ?? 0
}

function rememberSeason(number: number): void {
  try {
    localStorage.setItem(seasonStorageKey.value, String(number))
  } catch {
    // Season navigation remains usable when browser storage is unavailable.
  }
}

function readAutoNext(): boolean {
  try {
    return localStorage.getItem('kadr:auto-next') === 'true'
  } catch {
    return false
  }
}

function setAutoNext(value: boolean): void {
  autoNext.value = value
  try {
    localStorage.setItem('kadr:auto-next', String(value))
  } catch {
    // The preference remains active for the current page.
  }
}

async function loadSeason(resetPlayback = true): Promise<void> {
  if (!media.value || media.value.kind !== 'series') return
  const requestId = ++seasonRequestId
  seasonLoading.value = true
  seasonError.value = ''
  if (resetPlayback) {
    selectedEpisode.value = null
    playback.value = null
    playbackMessage.value = ''
  }
  try {
    const result = await getSeriesSeason(media.value.id, selectedSeasonNumber.value)
    if (requestId === seasonRequestId) seasonDetails.value = result
  } catch (caught) {
    if (requestId === seasonRequestId) {
      seasonDetails.value = null
      seasonError.value = friendlyApiError(caught)
    }
  } finally {
    if (requestId === seasonRequestId) seasonLoading.value = false
  }
}

function selectSeason(number: number): void {
  if (number === selectedSeasonNumber.value) return
  selectedSeasonNumber.value = number
  rememberSeason(number)
  void loadSeason()
}

async function openPlaybackFlow(episode: EpisodeSummary | null = null): Promise<void> {
  if (!media.value || playbackLoading.value) return
  selectedEpisode.value = episode
  nextEpisodeOpen.value = false
  nextEpisodeResult.value = null
  nextPrefetchStarted.value = false
  playback.value = null
  playbackMessage.value = ''
  playbackLoading.value = true
  try {
    const result = await resolvePlayback(media.value.id, media.value.kind, episode)
    if (result.status === 'ready' || result.status === 'buffering') {
      playback.value = result
      await nextTick()
      document.getElementById('resolved-playback')?.scrollIntoView({ behavior: 'smooth' })
      return
    }
    playbackMessage.value = result.message ?? 'Выберите источник для начала просмотра.'
    await openSourceSelector('playback')
  } catch (caught) {
    playbackMessage.value = friendlyApiError(caught)
  } finally {
    playbackLoading.value = false
  }
}

async function prepareNextEpisode(): Promise<void> {
  if (
    !media.value
    || !selectedEpisode.value
    || !playback.value
    || nextPrefetchStarted.value
  ) return
  nextPrefetchStarted.value = true
  try {
    await prefetchNextEpisode(
      media.value.id,
      selectedEpisode.value,
      playback.value.task_id,
      playback.value.file_id,
    )
  } catch {
    // Prefetch is opportunistic and must not interrupt current playback.
  }
}

async function showNextEpisode(): Promise<void> {
  if (!media.value || !selectedEpisode.value || !playback.value) return
  nextEpisodeOpen.value = true
  nextEpisodeLoading.value = true
  nextEpisodeResult.value = null
  try {
    nextEpisodeResult.value = await resolveNextEpisode(
      media.value.id,
      selectedEpisode.value,
      playback.value.task_id,
      playback.value.file_id,
    )
  } catch (caught) {
    nextEpisodeResult.value = {
      status: 'unavailable',
      episode: null,
      playback: null,
      prefetched: false,
      combined_file: false,
      message: friendlyApiError(caught),
    }
  } finally {
    nextEpisodeLoading.value = false
  }
}

async function playNextEpisode(): Promise<void> {
  const result = nextEpisodeResult.value
  if (!result?.episode || !result.playback || !media.value) return
  selectedEpisode.value = result.episode
  playback.value = result.playback
  playbackMessage.value = ''
  nextEpisodeOpen.value = false
  nextEpisodeResult.value = null
  nextPrefetchStarted.value = false
  if (selectedSeasonNumber.value !== result.episode.season_number) {
    selectedSeasonNumber.value = result.episode.season_number
    rememberSeason(result.episode.season_number)
    await loadSeason(false)
  }
  await nextTick()
  document.getElementById('resolved-playback')?.scrollIntoView({ behavior: 'smooth' })
}

async function chooseNextEpisodeSource(): Promise<void> {
  const episode = nextEpisodeResult.value?.episode
  if (!episode || !media.value) return
  selectedEpisode.value = episode
  playback.value = null
  playbackMessage.value = nextEpisodeResult.value?.message
    ?? 'Выберите источник для следующего эпизода.'
  nextEpisodeOpen.value = false
  nextEpisodeResult.value = null
  nextPrefetchStarted.value = false
  if (selectedSeasonNumber.value !== episode.season_number) {
    selectedSeasonNumber.value = episode.season_number
    rememberSeason(episode.season_number)
    await loadSeason(false)
  }
  await openSourceSelector('playback')
}

async function openSourceSelector(intent: 'playback' | 'season' = 'playback'): Promise<void> {
  if (!media.value) return
  sourceIntent.value = intent
  sourceSelectorOpen.value = true
  sourceSelectorError.value = ''
  await loadSourceOptions()
}

async function startSeasonDownload(): Promise<void> {
  if (!media.value || media.value.kind !== 'series' || sourceSelectorLoading.value) return
  seasonDownloadMessage.value = ''
  sourceTaskId.value = null
  sourceMatchReport.value = null
  sourceMatchOpen.value = false
  await openSourceSelector('season')
}

function closeSourceSelector(): void {
  sourceSelectorOpen.value = false
  sourceMatchOpen.value = false
  sourceIntent.value = 'playback'
}

async function loadSourceOptions(): Promise<void> {
  if (!media.value || sourceSelectorLoading.value) return
  sourceSelectorLoading.value = true
  sourceSelectorError.value = ''
  try {
    const seasonNumber = media.value.kind === 'series'
      ? sourceIntent.value === 'season'
        ? selectedSeasonNumber.value
        : selectedEpisode.value?.season_number ?? selectedSeasonNumber.value
      : null
    const result = await getSources(
      media.value.id,
      media.value.kind,
      'seeders',
      'desc',
      seasonNumber || undefined,
    )
    sourceItems.value = result.items
  } catch (caught) {
    sourceItems.value = []
    sourceSelectorError.value = friendlyApiError(caught)
  } finally {
    sourceSelectorLoading.value = false
  }
}

function targetIsConfirmed(report: EpisodeMatchReport): boolean {
  if (!selectedEpisode.value) return false
  return report.files.some((file) => file.confirmed && file.episodes.some((episode) => (
    episode.season_number === selectedEpisode.value?.season_number
    && episode.episode_number === selectedEpisode.value?.number
  )))
}

function reportContainsSeason(
  report: EpisodeMatchReport,
  confirmed: boolean,
): boolean {
  const seasonNumber = selectedSeasonNumber.value
  return report.files.some((file) => (
    !file.unsafe
    && file.confirmed === confirmed
    && [...file.episodes, ...file.alternatives].some(
      (episode) => episode.season_number === seasonNumber,
    )
  ))
}

async function finishSeasonDownload(report: EpisodeMatchReport): Promise<void> {
  if (!sourceTaskId.value) return
  const seasonNumber = selectedSeasonNumber.value
  const candidates = report.files
    .filter((file) => (
      file.confirmed
      && !file.unsafe
      && file.episodes.some((episode) => episode.season_number === seasonNumber)
    ))
    .sort((left, right) => {
      const leftEpisode = Math.min(...left.episodes
        .filter((episode) => episode.season_number === seasonNumber)
        .map((episode) => episode.episode_number))
      const rightEpisode = Math.min(...right.episodes
        .filter((episode) => episode.season_number === seasonNumber)
        .map((episode) => episode.episode_number))
      return leftEpisode - rightEpisode || left.file_id - right.file_id
    })
  if (!candidates.length) {
    sourceSelectorError.value = `В выбранном источнике не удалось распознать серии сезона ${seasonNumber}.`
    return
  }
  const fileIds = [...new Set(candidates.map((file) => file.file_id))]
  await selectTorrentFile(sourceTaskId.value, fileIds[0])
  await configureTorrentPrefetch(sourceTaskId.value, fileIds)
  const episodes = new Set(candidates.flatMap((file) => file.episodes
    .filter((episode) => episode.season_number === seasonNumber)
    .map((episode) => episode.episode_number)))
  seasonDownloadMessage.value = `Сезон ${seasonNumber} добавлен в загрузку. Эпизодов: ${episodes.size}.`
  closeSourceSelector()
}

async function waitForTorrentMetadata(taskId: string): Promise<boolean> {
  for (let attempt = 0; attempt < 8; attempt += 1) {
    const files = await getTorrentFiles(taskId)
    if (files.some((file) => file.is_video)) return true
    await new Promise((resolve) => window.setTimeout(resolve, 750))
  }
  return false
}

async function finishSourcePlayback(): Promise<void> {
  if (!media.value) return
  const result = await resolvePlayback(media.value.id, media.value.kind, selectedEpisode.value)
  if (result.status !== 'ready' && result.status !== 'buffering') {
    sourceSelectorError.value = result.message ?? 'Источник пока не готов к воспроизведению.'
    return
  }
  playback.value = result
  playbackMessage.value = ''
  sourceSelectorOpen.value = false
  sourceMatchOpen.value = false
  nextEpisodeResult.value = null
  nextEpisodeLoading.value = false
  nextEpisodeOpen.value = false
  nextPrefetchStarted.value = false
  await nextTick()
  document.getElementById('resolved-playback')?.scrollIntoView({ behavior: 'smooth' })
}

async function selectSource(source: SourceRelease): Promise<void> {
  if (!media.value || sourceBusyId.value) return
  sourceBusyId.value = source.id
  sourceSelectorError.value = ''
  try {
    const seasonNumber = media.value.kind === 'series'
      ? sourceIntent.value === 'season'
        ? selectedSeasonNumber.value
        : selectedEpisode.value?.season_number ?? selectedSeasonNumber.value
      : null
    const task = await addTorrent(
      media.value.id,
      media.value.kind,
      source.id,
      seasonNumber || null,
    )
    sourceTaskId.value = task.id
    if (!await waitForTorrentMetadata(task.id)) {
      sourceSelectorError.value = 'Метаданные раздачи ещё загружаются. Повторите выбор через несколько секунд.'
      return
    }
    if (media.value.kind === 'series') {
      sourceMatchReport.value = await analyzeEpisodeMatches(task.id)
      if (sourceIntent.value === 'season') {
        if (reportContainsSeason(sourceMatchReport.value, false)) {
          sourceMatchOpen.value = true
          return
        }
        await finishSeasonDownload(sourceMatchReport.value)
        return
      }
      if (selectedEpisode.value && !targetIsConfirmed(sourceMatchReport.value)) {
        sourceMatchOpen.value = true
        return
      }
      if (!selectedEpisode.value) {
        if (sourceMatchReport.value.requires_confirmation) sourceMatchOpen.value = true
        else {
          sourceSelectorOpen.value = false
          playbackMessage.value = 'Источник сохранён. Выберите эпизод для просмотра.'
        }
        return
      }
    }
    await finishSourcePlayback()
  } catch (caught) {
    sourceSelectorError.value = friendlyApiError(caught)
  } finally {
    sourceBusyId.value = null
  }
}

async function saveSourceMatches(mappings: EpisodeMatchSelection[]): Promise<void> {
  if (!sourceTaskId.value) return
  sourceBusyId.value = 'confirming'
  sourceSelectorError.value = ''
  try {
    sourceMatchReport.value = await confirmEpisodeMatches(sourceTaskId.value, mappings)
    if (sourceIntent.value === 'season') {
      if (reportContainsSeason(sourceMatchReport.value, false)) {
        sourceMatchOpen.value = true
        return
      }
      await finishSeasonDownload(sourceMatchReport.value)
      return
    }
    if (selectedEpisode.value && targetIsConfirmed(sourceMatchReport.value)) {
      await finishSourcePlayback()
      return
    }
    sourceMatchOpen.value = sourceMatchReport.value.requires_confirmation
    if (!selectedEpisode.value && !sourceMatchOpen.value) {
      sourceSelectorOpen.value = false
      playbackMessage.value = 'Источник и соответствия серий сохранены.'
    }
  } catch (caught) {
    sourceSelectorError.value = friendlyApiError(caught)
  } finally {
    sourceBusyId.value = null
  }
}

async function handlePrimaryAction(): Promise<void> {
  if (media.value?.kind === 'movie') {
    await openPlaybackFlow()
    return
  }
  await nextTick()
  document.getElementById('episodes-title')?.scrollIntoView({ behavior: 'smooth' })
}

async function loadDetails(): Promise<void> {
  const id = Number(route.params.id)
  if (!Number.isInteger(id) || id <= 0) {
    error.value = 'Некорректный идентификатор.'
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  seasonRequestId += 1
  seasonDetails.value = null
  seasonError.value = ''
  selectedEpisode.value = null
  playback.value = null
  playbackMessage.value = ''
  sourceSelectorOpen.value = false
  sourceIntent.value = 'playback'
  sourceSelectorError.value = ''
  sourceItems.value = []
  sourceBusyId.value = null
  sourceTaskId.value = null
  sourceMatchReport.value = null
  sourceMatchOpen.value = false
  seasonDownloadMessage.value = ''
  try {
    media.value = await getMediaDetails(kind.value, id)
    const favorites = await getFavorites()
    favorite.value = favorites.some((item) => item.media_id === id && item.media_kind === kind.value)
    if (media.value.kind === 'series' && availableSeasons.value.length) {
      selectedSeasonNumber.value = initialSeason()
      await loadSeason()
    }
  } catch (caught) {
    error.value = friendlyApiError(caught)
  } finally {
    loading.value = false
  }
}

async function toggleFavorite(): Promise<void> {
  if (!media.value || favoriteBusy.value) return
  favoriteBusy.value = true
  try {
    if (favorite.value) {
      await deleteFavorite(media.value.kind, media.value.id)
      favorite.value = false
    } else {
      await addFavorite({
        media_id: media.value.id,
        media_kind: media.value.kind,
        title: media.value.title,
        original_title: media.value.original_title,
        poster_url: media.value.poster_url,
        backdrop_url: media.value.backdrop_url,
      })
      favorite.value = true
    }
  } catch (caught) {
    error.value = friendlyApiError(caught)
  } finally {
    favoriteBusy.value = false
  }
}

watch(() => route.fullPath, loadDetails, { immediate: true })
</script>

<template>
  <div v-if="loading" class="page-container"><div class="hero-skeleton" /></div>
  <div v-else-if="error" class="page-container centered-state">
    <StatePanel
      title="Карточка недоступна"
      :message="error"
      show-retry
      @retry="loadDetails"
    />
  </div>
  <article v-else-if="media" class="details-page">
    <MediaHero :media="media">
      <MediaActions
        :play-label="media.kind === 'movie' ? 'Смотреть' : 'Выбрать эпизод'"
        :favorite="favorite"
        :favorite-busy="favoriteBusy"
        :trailer-url="media.trailer_url"
        @play="handlePrimaryAction"
        @toggle-favorite="toggleFavorite"
        @change-source="openSourceSelector"
      />
    </MediaHero>

    <section
      v-if="media.kind === 'series' && availableSeasons.length"
      class="details-section episodes-section"
      aria-labelledby="episodes-title"
    >
      <div class="episodes-heading">
        <h2 id="episodes-title">Эпизоды</h2>
        <div class="season-actions">
          <SeasonSelector
            :model-value="selectedSeasonNumber"
            :seasons="availableSeasons"
            :disabled="seasonLoading"
            @update:model-value="selectSeason"
          />
          <button
            class="button secondary focus-ring"
            type="button"
            :disabled="seasonLoading || sourceBusyId !== null"
            @click="startSeasonDownload"
          >
            Скачать сезон
          </button>
        </div>
      </div>
      <p v-if="seasonDownloadMessage" class="legacy-playback-notice" role="status">
        {{ seasonDownloadMessage }} <RouterLink class="text-link" to="/downloads">Открыть загрузки</RouterLink>
      </p>
      <p v-if="seasonDetails?.overview" class="season-overview">{{ seasonDetails.overview }}</p>
      <p v-if="playbackMessage && selectedEpisode" class="legacy-playback-notice" role="status">
        {{ playbackMessage }} Окно выбора источника открыто.
      </p>
      <EpisodeList
        :episodes="seasonDetails?.episodes ?? []"
        :loading="seasonLoading"
        :error="seasonError"
        @select="openPlaybackFlow"
        @retry="loadSeason"
      />
    </section>

    <section
      v-if="playbackLoading || (playback && playback.task_id)"
      id="resolved-playback"
      class="details-section"
      aria-label="Единый просмотр"
    >
      <StatePanel
        v-if="playbackLoading"
        title="Подготавливаем просмотр"
        message="Проверяем библиотеку, сохранённый источник и готовность буфера."
      />
      <KadrPlayer
        v-else-if="playback && playback.task_id"
        :key="`${playback.source}:${playback.task_id}:${playback.file_id ?? 'saved'}`"
        :task-id="playback.task_id"
        :title="media.title"
        :selection-label="selectedEpisode ? `Сезон ${selectedEpisode.season_number} · Серия ${selectedEpisode.number}` : media.title"
        :file-name="selectedEpisode?.name || media.title"
        :media-id="media.id"
        :media-kind="media.kind"
        :poster-url="media.poster_url"
        :file-id="playback.file_id ?? undefined"
        :episode="selectedEpisode"
        :download-progress="playback.download_progress"
        :download-state="playback.download_state ?? ''"
        :download-speed-bytes="playback.download_speed_bytes"
        :direct-stream-url="playback.source === 'library' ? playback.stream_url ?? '' : ''"
        :library-item-id="playback.source === 'library' ? playback.library_item_id ?? '' : ''"
        :initial-resume-seconds="playback.resume_position_seconds"
        auto-activate
        @near-end="prepareNextEpisode"
        @ended="showNextEpisode"
      />
    </section>

    <p v-if="playbackMessage && media.kind === 'movie'" class="details-section legacy-playback-notice" role="status">
      {{ playbackMessage }} Окно выбора источника открыто.
    </p>

    <section class="details-section download-management-link">
      <div>
        <p class="eyebrow">Фоновая загрузка</p>
        <h2>Управление перенесено в «Загрузки»</h2>
        <p>Скорость, очередь, файлы и остановка задач доступны отдельно от просмотра.</p>
      </div>
      <RouterLink class="button secondary focus-ring" to="/downloads">
        Открыть загрузки
      </RouterLink>
    </section>

    <SourceSelector
      v-if="sourceSelectorOpen"
      :title="sourceIntent === 'season'
        ? `${media.title} · Сезон ${selectedSeasonNumber}`
        : selectedEpisode
          ? `${media.title} · S${selectedEpisode.season_number}E${selectedEpisode.number}`
          : media.title"
      :items="sourceItems"
      :loading="sourceSelectorLoading"
      :busy-source-id="sourceBusyId"
      :error="sourceSelectorError"
      :eyebrow="sourceIntent === 'season' ? 'Загрузка сезона' : 'Источник просмотра'"
      :heading="sourceIntent === 'season' ? `Скачать сезон ${selectedSeasonNumber}` : 'Выберите источник'"
      :action-label="sourceIntent === 'season' ? 'Скачать сезон' : 'Выбрать'"
      @close="closeSourceSelector"
      @retry="loadSourceOptions"
      @select="selectSource"
    />
    <EpisodeMatchDialog
      v-if="sourceMatchOpen && sourceMatchReport"
      :report="sourceMatchReport"
      :busy="sourceBusyId === 'confirming'"
      :error="sourceSelectorError"
      @close="sourceMatchOpen = false"
      @confirm="saveSourceMatches"
    />
    <NextEpisodeOverlay
      v-if="nextEpisodeOpen"
      :result="nextEpisodeResult"
      :loading="nextEpisodeLoading"
      :auto-play="autoNext"
      @play="playNextEpisode"
      @choose-source="chooseNextEpisodeSource"
      @close="nextEpisodeOpen = false"
      @update:auto-play="setAutoNext"
    />

    <CastCarousel :cast="media.cast" />
  </article>
</template>
