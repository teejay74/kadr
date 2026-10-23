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
const hero = computed(() => popularMovies.value[0] ?? null)

async function loadHome(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const [movies, newest, series] = await Promise.all([
      getMediaPage('movie', { sort: 'popular' }),
      getMediaPage('movie', { sort: 'newest' }),
      getMediaPage('series', { sort: 'popular' }),
    ])
    popularMovies.value = movies.items
    newMovies.value = newest.items
    popularSeries.value = series.items
  } catch (caught) {
    error.value = friendlyApiError(caught)
  } finally {
    loading.value = false
  }
}

onMounted(loadHome)
</script>

<template>
  <div v-if="loading" class="page-container">
    <div class="hero-skeleton" aria-label="Загрузка каталога" />
  </div>
  <div v-else-if="error" class="page-container centered-state">
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
          <span>Фильм</span>
        </div>
        <p class="hero-overview">{{ hero.overview || 'Описание пока не переведено.' }}</p>
        <RouterLink class="button primary focus-ring" :to="`/movies/${hero.id}`">Подробнее</RouterLink>
      </div>
    </section>

    <div class="content-stack">
      <MediaRail title="Популярные фильмы" :items="popularMovies" more-to="/movies" />
      <MediaRail title="Новинки" :items="newMovies" more-to="/movies?sort=newest" />
      <MediaRail title="Сериалы" :items="popularSeries" more-to="/series" />
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
