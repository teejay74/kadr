<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import CastCarousel from '../components/CastCarousel.vue'
import EpisodeList from '../components/EpisodeList.vue'
import MediaActions from '../components/MediaActions.vue'
import MediaHero from '../components/MediaHero.vue'
import SeasonSelector from '../components/SeasonSelector.vue'
import StatePanel from '../components/StatePanel.vue'
import SourcesPanel from '../components/SourcesPanel.vue'
import {
  addFavorite,
  deleteFavorite,
  friendlyApiError,
  getFavorites,
  getMediaDetails,
  getSeriesSeason,
} from '../services/api'
import type {
  EpisodeSummary,
  MediaDetails,
  MediaKind,
  SeasonDetails,
  SeasonSummary,
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

async function loadSeason(): Promise<void> {
  if (!media.value || media.value.kind !== 'series') return
  const requestId = ++seasonRequestId
  seasonLoading.value = true
  seasonError.value = ''
  selectedEpisode.value = null
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
  selectedEpisode.value = episode
  await nextTick()
  document.getElementById('media-sources')?.scrollIntoView({ behavior: 'smooth' })
}

async function handlePrimaryAction(): Promise<void> {
  await nextTick()
  const target = media.value?.kind === 'series' ? 'episodes-title' : 'media-sources'
  document.getElementById(target)?.scrollIntoView({ behavior: 'smooth' })
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
      <p v-if="selectedEpisode" class="legacy-playback-notice" role="status">
        Выбрано: сезон {{ selectedEpisode.season_number }}, серия {{ selectedEpisode.number }}.
        До включения нового механизма запуска подтвердите соответствующий файл в блоке источника.
      </p>
      <EpisodeList
        :episodes="seasonDetails?.episodes ?? []"
        :loading="seasonLoading"
        :error="seasonError"
        @select="openPlaybackFlow"
        @retry="loadSeason"
      />
    </section>

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

    <CastCarousel :cast="media.cast" />
  </article>
</template>
