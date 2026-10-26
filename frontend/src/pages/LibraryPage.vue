<script setup lang="ts">
import { onMounted, ref } from 'vue'

import StatePanel from '../components/StatePanel.vue'
import KadrPlayer from '../components/KadrPlayer.vue'
import { deleteLibraryItem, friendlyApiError, getFavorites, getLibrary } from '../services/api'
import type { FavoriteItem, LibraryItem } from '../types/media'

const library = ref<LibraryItem[]>([])
const favorites = ref<FavoriteItem[]>([])
const loading = ref(true)
const error = ref('')

function formatBytes(bytes: number): string {
  const units = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']
  const unit = Math.min(Math.floor(Math.log(Math.max(bytes, 1)) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** unit).toFixed(unit > 2 ? 1 : 0)} ${units[unit]}`
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    ;[library.value, favorites.value] = await Promise.all([getLibrary(), getFavorites()])
  } catch (caught) {
    error.value = friendlyApiError(caught)
  } finally {
    loading.value = false
  }
}

async function remove(item: LibraryItem): Promise<void> {
  if (!window.confirm(`Удалить «${item.title}» из библиотеки? Файл будет удалён.`)) return
  try {
    await deleteLibraryItem(item.id)
    library.value = library.value.filter((candidate) => candidate.id !== item.id)
  } catch (caught) {
    error.value = friendlyApiError(caught)
  }
}

onMounted(load)
</script>

<template>
  <div class="page-container library-page">
    <div class="page-title-row">
      <div><p class="eyebrow">Локальное хранилище</p><h1>Моя библиотека</h1></div>
      <p>{{ library.length }} файлов · {{ formatBytes(library.reduce((sum, item) => sum + item.size_bytes, 0)) }}</p>
    </div>
    <StatePanel v-if="loading" title="Загружаем библиотеку" message="Читаем сохранённые фильмы и сериалы." />
    <StatePanel v-else-if="error" title="Библиотека недоступна" :message="error" show-retry @retry="load" />
    <section v-else-if="library.length" class="saved-grid">
      <article v-for="item in library" :key="item.id" class="saved-card">
        <img v-if="item.poster_url" :src="item.poster_url" :alt="item.title" />
        <div class="saved-copy">
          <p class="eyebrow">{{ item.media_kind === 'movie' ? 'Фильм' : 'Сериал' }}</p>
          <h2>{{ item.title }}</h2>
          <p>{{ formatBytes(item.size_bytes) }}</p>
          <KadrPlayer
            :task-id="item.task_id"
            :title="item.title"
            :file-name="item.original_title || item.title"
            :media-id="item.media_id"
            :media-kind="item.media_kind"
            :poster-url="item.poster_url"
            :download-progress="1"
            download-state="stoppedUP"
            :direct-stream-url="item.stream_url"
          />
          <div class="action-row">
            <RouterLink class="button secondary" :to="`/${item.media_kind === 'movie' ? 'movies' : 'series'}/${item.media_id}`">Карточка</RouterLink>
            <button class="button danger" type="button" @click="remove(item)">Удалить</button>
          </div>
        </div>
      </article>
    </section>
    <StatePanel v-else title="Библиотека пуста" message="Дождитесь полной загрузки видео и нажмите «Сохранить в библиотеку»." />

    <section v-if="favorites.length" class="details-section favorites-section">
      <h2>Избранное</h2>
      <div class="favorite-grid">
        <RouterLink v-for="item in favorites" :key="item.id" class="favorite-card" :to="`/${item.media_kind === 'movie' ? 'movies' : 'series'}/${item.media_id}`">
          <img v-if="item.poster_url" :src="item.poster_url" :alt="item.title" />
          <strong>{{ item.title }}</strong>
        </RouterLink>
      </div>
    </section>
  </div>
</template>
