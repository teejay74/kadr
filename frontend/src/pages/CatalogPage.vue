<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import MediaCard from '../components/MediaCard.vue'
import StatePanel from '../components/StatePanel.vue'
import { friendlyApiError, getGenres, getMediaPage } from '../services/api'
import type { Genre, MediaCardData, MediaKind, SortMode } from '../types/media'

const route = useRoute()
const router = useRouter()
const kind = computed(() => route.meta.kind as MediaKind)
const title = computed(() => (kind.value === 'movie' ? 'Фильмы' : 'Сериалы'))
const items = ref<MediaCardData[]>([])
const genres = ref<Genre[]>([])
const loading = ref(true)
const error = ref('')
const page = ref(1)
const totalPages = ref(0)
const sort = ref<SortMode>('popular')
const genre = ref<number | null>(null)
const year = ref<number | null>(null)
const genresFor = ref<MediaKind | null>(null)

function optionalPositiveInteger(value: unknown): number | null {
  const number = Number(value)
  return Number.isInteger(number) && number > 0 ? number : null
}

async function loadCatalog(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const result = await getMediaPage(kind.value, {
      page: page.value,
      sort: sort.value,
      genre: genre.value,
      year: year.value,
    })
    items.value = result.items
    totalPages.value = result.total_pages
  } catch (caught) {
    error.value = friendlyApiError(caught)
  } finally {
    loading.value = false
  }
}

async function initialize(): Promise<void> {
  const requestedPage = Number(route.query.page ?? 1)
  const requestedSort = route.query.sort
  page.value = Number.isInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1
  sort.value = ['popular', 'rating', 'newest'].includes(String(requestedSort))
    ? (requestedSort as SortMode)
    : 'popular'
  genre.value = optionalPositiveInteger(route.query.genre)
  year.value = optionalPositiveInteger(route.query.year)
  if (genresFor.value !== kind.value) {
    try {
      genres.value = await getGenres(kind.value)
      genresFor.value = kind.value
    } catch {
      genres.value = []
    }
  }
  await loadCatalog()
}

function applyFilters(): void {
  void router.replace({
    query: {
      sort: sort.value,
      ...(genre.value ? { genre: String(genre.value) } : {}),
      ...(year.value ? { year: String(year.value) } : {}),
    },
  })
}

function changePage(next: number): void {
  void router.replace({ query: { ...route.query, page: String(next) } })
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

watch(() => route.fullPath, initialize, { immediate: true })
</script>

<template>
  <div class="page-container catalog-page">
    <div class="page-title-row">
      <div><p class="eyebrow">Каталог</p><h1>{{ title }}</h1></div>
      <form class="filters" @submit.prevent="applyFilters">
        <label><span>Сортировка</span><select v-model="sort"><option value="popular">По популярности</option><option value="rating">По рейтингу</option><option value="newest">Сначала новые</option></select></label>
        <label><span>Жанр</span><select v-model="genre"><option :value="null">Все жанры</option><option v-for="item in genres" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
        <label><span>Год</span><input v-model.number="year" type="number" min="1870" max="2100" placeholder="Любой" /></label>
        <button class="button secondary focus-ring" type="submit">Применить</button>
      </form>
    </div>
    <div v-if="loading" class="poster-grid" aria-label="Загрузка"><div v-for="index in 10" :key="index" class="card-skeleton" /></div>
    <StatePanel
      v-else-if="error"
      title="Не удалось загрузить каталог"
      :message="error"
      show-retry
      @retry="loadCatalog"
    />
    <div v-else-if="items.length" class="poster-grid"><MediaCard v-for="media in items" :key="`${media.kind}-${media.id}`" :media="media" /></div>
    <StatePanel v-else title="Ничего не найдено" message="Попробуйте изменить фильтры." />
    <nav v-if="!loading && !error && totalPages > 1" class="pagination" aria-label="Страницы каталога">
      <button class="button secondary focus-ring" :disabled="page <= 1" @click="changePage(page - 1)">← Назад</button>
      <span>{{ page }} / {{ totalPages }}</span>
      <button class="button secondary focus-ring" :disabled="page >= totalPages" @click="changePage(page + 1)">Далее →</button>
    </nav>
  </div>
</template>
