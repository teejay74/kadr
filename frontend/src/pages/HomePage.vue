<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import MediaRail from '../components/MediaRail.vue'
import StatePanel from '../components/StatePanel.vue'
import { friendlyApiError, getMediaPage } from '../services/api'
import type { MediaCardData } from '../types/media'

const popularMovies = ref<MediaCardData[]>([])
const newMovies = ref<MediaCardData[]>([])
const popularSeries = ref<MediaCardData[]>([])
const loading = ref(true)
const error = ref('')
const hero = computed(() => popularMovies.value[0] ?? newMovies.value[0] ?? popularSeries.value[0])

async function loadHome(): Promise<void> {
  loading.value = true
  error.value = ''
  const results = await Promise.allSettled([
    getMediaPage('movie', { sort: 'popular' }),
    getMediaPage('movie', { sort: 'newest', releasedWithinDays: 365 }),
    getMediaPage('series', { sort: 'popular' }),
  ])
  const [movies, newest, series] = results
  if (movies.status === 'fulfilled') popularMovies.value = movies.value.items
  if (newest.status === 'fulfilled') newMovies.value = newest.value.items
  if (series.status === 'fulfilled') popularSeries.value = series.value.items
  const failure = results.find((result) => result.status === 'rejected')
  if (failure) error.value = friendlyApiError(failure.reason)
  loading.value = false
}

onMounted(loadHome)
</script>

<template>
  <div v-if="loading" class="page-container">
    <div class="hero-skeleton" aria-label="Загрузка каталога" />
  </div>
  <div v-else-if="error && !hero" class="page-container centered-state">
    <StatePanel title="Каталог ждёт подключения" :message="error" show-retry @retry="loadHome" />
  </div>
  <div v-else-if="hero" class="home-page">
    <section
      class="featured-hero"
      :style="hero.backdrop_url ? { backgroundImage: `linear-gradient(90deg, rgba(16,17,22,.98) 8%, rgba(16,17,22,.58) 55%, rgba(16,17,22,.82)), url(${hero.backdrop_url})` } : {}"
    >
      <div class="hero-content">
        <p class="eyebrow">Сейчас в центре внимания</p>
        <h1>{{ hero.title }}</h1>
        <div class="hero-meta">
          <span v-if="hero.year">{{ hero.year }}</span>
          <span v-if="hero.rating">★ {{ hero.rating.toFixed(1) }}</span>
          <span>{{ hero.kind === 'movie' ? 'Фильм' : 'Сериал' }}</span>
        </div>
        <p class="hero-overview">{{ hero.overview || 'Описание пока не переведено.' }}</p>
        <RouterLink class="button primary focus-ring" :to="`/${hero.kind === 'movie' ? 'movies' : 'series'}/${hero.id}`">Подробнее</RouterLink>
      </div>
    </section>

    <div class="content-stack">
      <p v-if="error" role="status">
        Часть подборок временно недоступна.
        <button class="button secondary focus-ring" type="button" @click="loadHome">Повторить</button>
      </p>
      <MediaRail v-if="popularMovies.length" title="Популярные фильмы" :items="popularMovies" more-to="/movies" />
      <MediaRail v-if="newMovies.length" title="Новинки" :items="newMovies" more-to="/new" />
      <MediaRail v-if="popularSeries.length" title="Сериалы" :items="popularSeries" more-to="/series" />
    </div>
  </div>
  <div v-else class="page-container centered-state">
    <StatePanel
      title="Каталог пока пуст"
      message="TMDB не вернул доступных материалов."
      show-retry
      @retry="loadHome"
    />
  </div>
</template>
