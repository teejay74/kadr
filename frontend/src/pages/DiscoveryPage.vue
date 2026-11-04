<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import MediaCard from '../components/MediaCard.vue'
import StatePanel from '../components/StatePanel.vue'
import { friendlyApiError, getMediaPage } from '../services/api'
import type { AgeRating, MediaCardData, SortMode } from '../types/media'

type CollectionKind = 'new' | 'cartoons'

const route = useRoute()
const router = useRouter()
const collection = computed(() => route.meta.collection as CollectionKind)
const movies = ref<MediaCardData[]>([])
const series = ref<MediaCardData[]>([])
const loading = ref(true)
const error = ref('')
const sort = ref<SortMode>('newest')
const ageRating = ref<AgeRating | null>(null)
const title = computed(() => (collection.value === 'new' ? 'Новинки' : 'Мультфильмы'))

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  const isCartoons = collection.value === 'cartoons'
  const requestedSort = String(route.query.sort ?? (isCartoons ? 'popular' : 'newest'))
  sort.value = ['popular', 'rating', 'newest'].includes(requestedSort)
    ? (requestedSort as SortMode)
    : isCartoons ? 'popular' : 'newest'
  const requestedAge = String(route.query.age ?? '')
  ageRating.value = ['0+', '6+', '12+', '16+', '18+'].includes(requestedAge)
    ? (requestedAge as AgeRating)
    : null
  try {
    const common = {
      sort: sort.value,
      genre: isCartoons ? 16 : null,
      releasedWithinDays: isCartoons ? null : 365,
    }
    const [moviePage, seriesPage] = await Promise.all([
      getMediaPage('movie', { ...common, ageRating: isCartoons ? ageRating.value : null }),
      getMediaPage('series', common),
    ])
    movies.value = moviePage.items
    series.value = seriesPage.items
  } catch (caught) {
    error.value = friendlyApiError(caught)
  } finally {
    loading.value = false
  }
}

function applyFilters(): void {
  void router.replace({
    query: {
      sort: sort.value,
      ...(collection.value === 'cartoons' && ageRating.value ? { age: ageRating.value } : {}),
    },
  })
}

watch(() => route.fullPath, load, { immediate: true })
</script>

<template>
  <div class="page-container catalog-page discovery-page">
    <div class="page-title-row">
      <div>
        <p class="eyebrow">Подборка</p>
        <h1>{{ title }}</h1>
        <p v-if="collection === 'new'" class="page-description">Цифровые релизы фильмов и новые сериалы за последние 12 месяцев.</p>
        <p v-else class="page-description">Анимационные фильмы и сериалы. Возраст применяется к фильмам с российской маркировкой.</p>
      </div>
      <form class="filters" @submit.prevent="applyFilters">
        <label><span>Сортировка</span><select v-model="sort"><option value="popular">По популярности</option><option value="rating">По рейтингу</option><option value="newest">Сначала новые</option></select></label>
        <label v-if="collection === 'cartoons'"><span>Возраст</span><select v-model="ageRating"><option :value="null">Любой</option><option value="0+">0+</option><option value="6+">6+</option><option value="12+">12+</option><option value="16+">16+</option><option value="18+">18+</option></select></label>
        <button class="button secondary focus-ring" type="submit">Применить</button>
      </form>
    </div>
    <div v-if="loading" class="poster-grid" aria-label="Загрузка"><div v-for="index in 10" :key="index" class="card-skeleton" /></div>
    <StatePanel v-else-if="error" title="Не удалось загрузить подборку" :message="error" show-retry @retry="load" />
    <template v-else-if="movies.length || series.length">
      <section v-if="movies.length" class="search-group"><h2>Фильмы</h2><div class="poster-grid"><MediaCard v-for="item in movies" :key="`movie-${item.id}`" :media="item" /></div></section>
      <section v-if="series.length" class="search-group"><h2>Сериалы</h2><div class="poster-grid"><MediaCard v-for="item in series" :key="`series-${item.id}`" :media="item" /></div></section>
    </template>
    <StatePanel v-else title="Подборка пока пуста" message="Попробуйте изменить фильтры." />
  </div>
</template>
