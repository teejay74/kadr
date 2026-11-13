<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { RouteLocationRaw } from 'vue-router'

import MediaStatus from '../components/MediaStatus.vue'
import PlaybackProgress from '../components/PlaybackProgress.vue'
import StatePanel from '../components/StatePanel.vue'
import { friendlyApiError, getHistory } from '../services/api'
import type { HistoryItem } from '../types/media'
import { formatPlaybackTime } from '../utils/formatPlaybackTime'

const filters = [
  { id: 'all', label: 'Все' },
  { id: 'in-progress', label: 'В процессе' },
  { id: 'completed', label: 'Просмотрено' },
] as const
const filter = ref<(typeof filters)[number]['id']>('all')
const items = ref<HistoryItem[]>([])
const loading = ref(true)
const error = ref('')
const dateFormat = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' })

const visibleItems = computed(() => items.value.filter((item) => {
  if (filter.value === 'completed') return item.completed
  if (filter.value === 'in-progress') return isInProgress(item)
  return true
}))

function isInProgress(item: HistoryItem): boolean {
  return !item.completed && item.position_seconds > 0
}

function canResume(item: HistoryItem): boolean {
  return isInProgress(item)
    && (item.media_kind === 'movie' || (item.season_number !== null && item.episode_number !== null))
}

function detailsLink(item: HistoryItem, resume = false): RouteLocationRaw {
  return {
    name: item.media_kind === 'movie' ? 'movie-details' : 'series-details',
    params: { id: item.media_id },
    query: {
      season: item.season_number ?? undefined,
      episode: resume ? item.episode_number ?? undefined : undefined,
      resume: resume ? '1' : undefined,
    },
  }
}

function utcTimestamp(value: string): string {
  // SQLite history timestamps without an offset are stored in UTC.
  return /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    items.value = await getHistory()
  } catch (caught) {
    error.value = friendlyApiError(caught)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="history-heading">
      <h1>Продолжить просмотр</h1>
      <p>Журнал просмотра</p>
    </div>

    <StatePanel v-if="loading" title="Загружаем журнал просмотра" />
    <StatePanel v-else-if="error" title="Журнал недоступен" :message="error" show-retry @retry="load" />
    <StatePanel
      v-else-if="!items.length"
      title="Журнал пока пуст"
      message="Здесь появятся фильмы и серии, которые вы начали смотреть."
    />
    <template v-else>
      <div class="history-filters action-row" role="group" aria-label="Фильтр журнала просмотра">
        <button
          v-for="option in filters"
          :key="option.id"
          class="button focus-ring"
          :class="filter === option.id ? 'primary' : 'secondary'"
          type="button"
          :aria-pressed="filter === option.id"
          @click="filter = option.id"
        >
          {{ option.label }}
        </button>
      </div>
      <StatePanel v-if="!visibleItems.length" title="В этом фильтре пока нет записей" />
      <ol v-else class="history-list">
        <li v-for="item in visibleItems" :key="item.id" class="history-entry">
          <div class="history-poster">
            <img v-if="item.poster_url" :src="item.poster_url" alt="" loading="lazy" />
          </div>
          <div class="history-copy">
            <h2><RouterLink class="focus-ring" :to="detailsLink(item)">{{ item.title }}</RouterLink></h2>
            <p v-if="item.season_number !== null && item.episode_number !== null">
              Сезон {{ item.season_number }} · Серия {{ item.episode_number }}
            </p>
            <p v-else>{{ item.media_kind === 'movie' ? 'Фильм' : 'Сериал' }}</p>
            <time :datetime="utcTimestamp(item.updated_at)">
              {{ dateFormat.format(new Date(utcTimestamp(item.updated_at))) }}
            </time>
            <MediaStatus v-if="item.completed" status="completed" />
            <template v-else-if="isInProgress(item)">
              <p>
                {{ formatPlaybackTime(item.position_seconds) }}
                <template v-if="item.duration_seconds > 0"> / {{ formatPlaybackTime(item.duration_seconds) }}</template>
              </p>
              <PlaybackProgress :position-seconds="item.position_seconds" :duration-seconds="item.duration_seconds" />
            </template>
            <p v-else>Без сохранённой позиции</p>
          </div>
          <RouterLink v-if="canResume(item)" class="button primary focus-ring" :to="detailsLink(item, true)">
            Продолжить
          </RouterLink>
          <RouterLink
            v-else-if="isInProgress(item)"
            class="button secondary focus-ring"
            :to="detailsLink(item)"
          >
            Выбрать эпизод
          </RouterLink>
        </li>
      </ol>
    </template>
  </div>
</template>
