<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import MediaCard from '../components/MediaCard.vue'
import StatePanel from '../components/StatePanel.vue'
import { friendlyApiError, getMediaPage } from '../services/api'
import type { AgeRating, CatalogQuery, MediaKind, MediaPage, SortMode } from '../types/media'

type CollectionKind = 'new' | 'cartoons'

interface DiscoverySection {
  kind: MediaKind
  title: string
  moreLabel: string
  query: CatalogQuery
  result: MediaPage | null
  loadingMore: boolean
  error: string
}

const route = useRoute()
const router = useRouter()
const collection = computed(() => route.meta.collection as CollectionKind)
const sections = ref<DiscoverySection[]>([])
const visibleSections = computed(() => sections.value.filter((section) => section.result?.items.length))
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
  const common: CatalogQuery = {
    sort: sort.value,
    genre: isCartoons ? 16 : null,
    releasedWithinDays: isCartoons ? null : 365,
  }
  sections.value = [
    {
      kind: 'movie', title: 'Фильмы', moreLabel: 'Показать ещё фильмы',
      query: { ...common, ageRating: isCartoons ? ageRating.value : null },
      result: null, loadingMore: false, error: '',
    },
    {
      kind: 'series', title: 'Сериалы', moreLabel: 'Показать ещё сериалы',
      query: common,
      result: null, loadingMore: false, error: '',
    },
  ]
  const currentSections = sections.value
  try {
    const results = await Promise.all(
      currentSections.map((section) => getMediaPage(section.kind, section.query)),
    )
    currentSections.forEach((section, index) => { section.result = results[index] })
  } catch (caught) {
    if (currentSections === sections.value) error.value = friendlyApiError(caught)
  } finally {
    if (currentSections === sections.value) loading.value = false
  }
}

async function loadMore(section: DiscoverySection): Promise<void> {
  const current = section.result
  if (!current || section.loadingMore || current.page >= current.total_pages) return

  section.loadingMore = true
  section.error = ''
  try {
    const next = await getMediaPage(section.kind, { ...section.query, page: current.page + 1 })
    const items = new Map([...current.items, ...next.items].map((item) => [item.id, item]))
    section.result = {
      ...next,
      items: [...items.values()],
    }
  } catch (caught) {
    section.error = friendlyApiError(caught)
  } finally {
    section.loadingMore = false
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
    <template v-else-if="visibleSections.length">
      <section v-for="section in visibleSections" :key="section.kind" class="search-group" :aria-label="section.title">
        <h2>{{ section.title }}</h2>
        <div class="poster-grid" :aria-busy="section.loadingMore">
          <MediaCard v-for="item in section.result?.items" :key="item.id" :media="item" />
        </div>
        <div v-if="section.result && section.result.page < section.result.total_pages" class="pagination">
          <p v-if="section.error" role="alert">{{ section.error }}</p>
          <button
            class="button secondary focus-ring"
            type="button"
            :aria-label="section.moreLabel"
            :aria-disabled="section.loadingMore"
            @click="loadMore(section)"
          >
            {{ section.loadingMore ? 'Загрузка…' : 'Показать ещё' }}
          </button>
        </div>
      </section>
    </template>
    <StatePanel v-else title="Подборка пока пуста" message="Попробуйте изменить фильтры." />
  </div>
</template>
