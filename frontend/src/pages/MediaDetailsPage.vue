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
import SourcesPanel from '../components/SourcesPanel.vue'
import SourceSelector from '../components/SourceSelector.vue'
import {
  addTorrent,
  addFavorite,
  analyzeEpisodeMatches,
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
const sourceSelectorLoading = ref(false)
const sourceSelectorError = ref('')
const sourceItems = ref<SourceRelease[]>([])
const sourceBusyId = ref<string | null>(null)
const sourceTaskId = ref<string | null>(null)
const sourceMatchReport = ref<EpisodeMatchReport | null>(null)
const sourceMatchOpen = ref(false)
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
    await openSourceSelector()
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
  await openSourceSelector()
}

async function openSourceSelector(): Promise<void> {
  if (!media.value) return
  sourceSelectorOpen.value = true
  sourceSelectorError.value = ''
  await loadSourceOptions()
}

async function loadSourceOptions(): Promise<void> {
  if (!media.value || sourceSelectorLoading.value) return
  sourceSelectorLoading.value = true
  sourceSelectorError.value = ''
  try {
    const seasonNumber = media.value.kind === 'series'
      ? selectedEpisode.value?.season_number ?? selectedSeasonNumber.value
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
      ? selectedEpisode.value?.season_number ?? selectedSeasonNumber.value
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
  sourceSelectorError.value = ''
  sourceItems.value = []
  sourceBusyId.value = null
  sourceTaskId.value = null
  sourceMatchReport.value = null
  sourceMatchOpen.value = false
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
        <SeasonSelector
          :model-value="selectedSeasonNumber"
          :seasons="availableSeasons"
          :disabled="seasonLoading"
          @update:model-value="selectSeason"
        />
      </div>
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
        :initial-resume-seconds="playback.resume_position_seconds"
        auto-activate
        @near-end="prepareNextEpisode"
        @ended="showNextEpisode"
      />
    </section>

    <p v-if="playbackMessage && media.kind === 'movie'" class="details-section legacy-playback-notice" role="status">
      {{ playbackMessage }} Окно выбора источника открыто.
    </p>

    <SourcesPanel
      :media-id="media.id"
      :kind="media.kind"
      :title="media.title"
      :original-title="media.original_title"
      :poster-url="media.poster_url"
      :backdrop-url="media.backdrop_url"
      :seasons="media.seasons"
      :episode="selectedEpisode"
    />

    <SourceSelector
      v-if="sourceSelectorOpen"
      :title="selectedEpisode ? `${media.title} · S${selectedEpisode.season_number}E${selectedEpisode.number}` : media.title"
      :items="sourceItems"
      :loading="sourceSelectorLoading"
      :busy-source-id="sourceBusyId"
      :error="sourceSelectorError"
      @close="sourceSelectorOpen = false"
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
