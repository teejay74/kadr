<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import {
  addTorrent,
  friendlyApiError,
  getSources,
  getTorrent,
  getTorrentFiles,
  selectTorrentFile,
  startTorrent,
  stopTorrent,
} from '../services/api'
import type { MediaKind, SourceRelease, SourceSort, TorrentFile, TorrentStatus } from '../types/media'
import StatePanel from './StatePanel.vue'

const props = defineProps<{ mediaId: number; kind: MediaKind }>()
const items = ref<SourceRelease[]>([])
const query = ref('')
const loading = ref(false)
const error = ref('')
const searched = ref(false)
const sort = ref<SourceSort>('seeders')
const order = computed(() => (sort.value === 'title' ? 'asc' : 'desc'))
const torrent = ref<TorrentStatus | null>(null)
const torrentFiles = ref<TorrentFile[]>([])
const torrentBusy = ref(false)
const torrentError = ref('')

function formatBytes(bytes: number): string {
  if (bytes <= 0) return 'Размер неизвестен'
  const units = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']
  const unit = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** unit).toFixed(unit > 2 ? 1 : 0)} ${units[unit]}`
}

async function addSource(sourceId: string): Promise<void> {
  torrentBusy.value = true
  torrentError.value = ''
  try {
    torrent.value = await addTorrent(props.mediaId, props.kind, sourceId)
    await refreshFiles()
  } catch (caught) {
    torrentError.value = friendlyApiError(caught)
  } finally {
    torrentBusy.value = false
  }
}

async function refreshFiles(): Promise<void> {
  if (!torrent.value) return
  try {
    torrentFiles.value = await getTorrentFiles(torrent.value.id)
  } catch (caught) {
    torrentFiles.value = []
    torrentError.value = friendlyApiError(caught)
  }
}

async function chooseFile(fileId: number): Promise<void> {
  if (!torrent.value) return
  torrentBusy.value = true
  torrentError.value = ''
  try {
    torrent.value = await selectTorrentFile(torrent.value.id, fileId)
  } catch (caught) {
    torrentError.value = friendlyApiError(caught)
  } finally {
    torrentBusy.value = false
  }
}

async function applyTorrentAction(action: 'start' | 'stop' | 'refresh'): Promise<void> {
  if (!torrent.value) return
  torrentBusy.value = true
  torrentError.value = ''
  try {
    torrent.value = action === 'start'
      ? await startTorrent(torrent.value.id)
      : action === 'stop'
        ? await stopTorrent(torrent.value.id)
        : await getTorrent(torrent.value.id)
  } catch (caught) {
    torrentError.value = friendlyApiError(caught)
  } finally {
    torrentBusy.value = false
  }
}

async function loadSources(): Promise<void> {
  loading.value = true
  searched.value = true
  error.value = ''
  try {
    const result = await getSources(props.mediaId, props.kind, sort.value, order.value)
    items.value = result.items
    query.value = result.query
  } catch (caught) {
    items.value = []
    error.value = friendlyApiError(caught)
  } finally {
    loading.value = false
  }
}

watch(sort, () => {
  if (searched.value) void loadSources()
})
</script>

<template>
  <section class="details-section sources-section">
    <div class="sources-heading">
      <div>
        <p class="eyebrow">Prowlarr</p>
        <h2>Доступные источники</h2>
      </div>
      <label v-if="searched" class="source-sort">
        <span>Сортировка</span>
        <select v-model="sort">
          <option value="seeders">По сидам</option>
          <option value="resolution">По разрешению</option>
          <option value="source">По источнику</option>
          <option value="size">По размеру</option>
          <option value="title">По названию</option>
        </select>
      </label>
    </div>

    <div v-if="!searched" class="source-intro">
      <p>Поиск выполняется вручную через настроенные индексаторы и может занять несколько секунд.</p>
      <button class="button primary focus-ring" type="button" @click="loadSources">
        Найти источники
      </button>
    </div>
    <div v-else-if="loading" class="source-loading" role="status">Ищем доступные релизы…</div>
    <StatePanel
      v-else-if="error"
      title="Поиск источников недоступен"
      :message="error"
      show-retry
      @retry="loadSources"
    />
    <StatePanel
      v-else-if="items.length === 0"
      title="Релизы не найдены"
      :message="`По запросу «${query}» настроенные индексаторы ничего не вернули.`"
      show-retry
      @retry="loadSources"
    />
    <div v-else class="source-results">
      <p class="source-summary">Найдено: {{ items.length }} · запрос «{{ query }}»</p>
      <article v-for="item in items" :key="item.id" class="source-release">
        <div class="source-release-main">
          <h3>{{ item.title }}</h3>
          <p>{{ item.indexer }} · {{ formatBytes(item.size_bytes) }}</p>
          <div class="release-tags">
            <span v-if="item.resolution">{{ item.resolution }}</span>
            <span v-if="item.source">{{ item.source }}</span>
            <span v-if="item.codec">{{ item.codec }}</span>
            <span v-if="item.hdr_format">{{ item.hdr_format }}</span>
            <span v-if="item.audio">{{ item.audio }}</span>
            <span v-if="item.language">{{ item.language }}</span>
            <span v-if="item.release_type">{{ item.release_type }}</span>
          </div>
        </div>
        <dl class="source-health">
          <div><dt>Сиды</dt><dd>{{ item.seeders ?? '—' }}</dd></div>
          <div><dt>Пиры</dt><dd>{{ item.peers ?? '—' }}</dd></div>
        </dl>
        <button
          class="button source-add focus-ring"
          type="button"
          :disabled="torrentBusy || torrent !== null"
          @click="addSource(item.id)"
        >
          Добавить
        </button>
      </article>
      <p class="source-stage-note">Задача остановится после получения метаданных. Загрузка видео начнётся только после выбора файла.</p>
    </div>

    <section v-if="torrent" class="torrent-panel" aria-live="polite">
      <div class="sources-heading">
        <div>
          <p class="eyebrow">qBittorrent</p>
          <h3>{{ torrent.name }}</h3>
        </div>
        <strong>{{ Math.round(torrent.progress * 100) }}%</strong>
      </div>
      <progress :value="torrent.progress" max="1" />
      <p>Состояние: {{ torrent.state }} · сиды {{ torrent.seeds }} · пиры {{ torrent.peers }}</p>
      <div class="torrent-actions">
        <button class="button focus-ring" type="button" :disabled="torrentBusy" @click="refreshFiles">Обновить файлы</button>
        <button class="button focus-ring" type="button" :disabled="torrentBusy" @click="applyTorrentAction('refresh')">Обновить прогресс</button>
        <button v-if="torrent.can_start" class="button primary focus-ring" type="button" :disabled="torrentBusy" @click="applyTorrentAction('start')">Запустить</button>
        <button v-if="torrent.can_stop" class="button focus-ring" type="button" :disabled="torrentBusy" @click="applyTorrentAction('stop')">Остановить</button>
      </div>
      <div v-if="torrentFiles.length" class="torrent-files">
        <button
          v-for="file in torrentFiles"
          :key="file.id"
          class="torrent-file focus-ring"
          :class="{ selected: torrent.selected_file_id === file.id }"
          type="button"
          :disabled="torrentBusy || !file.is_video"
          @click="chooseFile(file.id)"
        >
          <span>{{ file.name }}</span>
          <small>{{ formatBytes(file.size_bytes) }}{{ file.is_video ? '' : ' · не видео' }}</small>
        </button>
      </div>
      <p v-else>Метаданные файлов ещё не получены. Нажмите «Обновить файлы» через несколько секунд.</p>
    </section>
    <p v-if="torrentError" class="torrent-error" role="alert">{{ torrentError }}</p>
  </section>
</template>
