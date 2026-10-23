<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import MediaCard from '../components/MediaCard.vue'
import StatePanel from '../components/StatePanel.vue'
import { friendlyApiError, searchMedia } from '../services/api'
import type { MediaCardData } from '../types/media'

const route = useRoute()
const query = computed(() => String(route.query.q ?? '').trim())
const movies = ref<MediaCardData[]>([])
const series = ref<MediaCardData[]>([])
const loading = ref(false)
const error = ref('')

async function search(): Promise<void> {
  if (query.value.length < 2) {
    movies.value = []
    series.value = []
    error.value = ''
    return
  }
  loading.value = true
  error.value = ''
  try {
    const [moviePage, seriesPage] = await Promise.all([
      searchMedia('movie', query.value),
      searchMedia('series', query.value),
    ])
    movies.value = moviePage.items
    series.value = seriesPage.items
  } catch (caught) {
    error.value = friendlyApiError(caught)
  } finally {
    loading.value = false
  }
}

watch(query, search, { immediate: true })
</script>

<template>
  <div class="page-container search-page">
    <p class="eyebrow">Результаты поиска</p><h1>«{{ query }}»</h1>
    <div v-if="loading" class="poster-grid"><div v-for="index in 10" :key="index" class="card-skeleton" /></div>
    <StatePanel
      v-else-if="error"
      title="Поиск недоступен"
      :message="error"
      show-retry
      @retry="search"
    />
    <template v-else-if="movies.length || series.length">
      <section v-if="movies.length" class="search-group"><h2>Фильмы</h2><div class="poster-grid"><MediaCard v-for="item in movies" :key="`movie-${item.id}`" :media="item" /></div></section>
      <section v-if="series.length" class="search-group"><h2>Сериалы</h2><div class="poster-grid"><MediaCard v-for="item in series" :key="`series-${item.id}`" :media="item" /></div></section>
    </template>
    <StatePanel v-else title="Совпадений нет" message="Проверьте написание или попробуйте оригинальное название." />
  </div>
</template>
