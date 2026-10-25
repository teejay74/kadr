<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  addTorrent,
  friendlyApiError,
  getMediaTorrent,
  getSources,
  getTorrent,
  getTorrentFiles,
  selectTorrentFile,
  saveToLibrary,
  startTorrent,
  stopTorrent,
} from '../services/api'
import type { MediaKind, SourceRelease, SourceSort, TorrentFile, TorrentStatus } from '../types/media'
import KadrPlayer from './KadrPlayer.vue'
import StatePanel from './StatePanel.vue'

const props = withDefaults(defineProps<{
  mediaId: number
  kind: MediaKind
  title?: string
  originalTitle?: string
  posterUrl?: string | null
  backdropUrl?: string | null
}>(), { title: '', originalTitle: '', posterUrl: null, backdropUrl: null })
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
const librarySaved = ref(false)
let torrentTimer: ReturnType<typeof setTimeout> | undefined
const dismissedTask = 'dismissed'

const videoFiles = computed(() => torrentFiles.value.filter((file) => file.is_video))
const selectedFile = computed(() => videoFiles.value.find(
  (file) => file.id === torrent.value?.selected_file_id,
))
const skippedFileCount = computed(() => torrentFiles.value.length - videoFiles.value.length)
const hasSelectedFile = computed(() => torrent.value?.selected_file_id !== null
  && torrent.value?.selected_file_id !== undefined)
const taskStorageKey = computed(() => `kadr:torrent:${props.kind}:${props.mediaId}`)

function formatBytes(bytes: number): string {
  if (bytes <= 0) return 'Размер неизвестен'
  const units = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']
  const unit = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** unit).toFixed(unit > 2 ? 1 : 0)} ${units[unit]}`
}

function formatSpeed(bytes: number): string {
  return bytes > 0 ? `${formatBytes(bytes)}/с` : 'ожидание источников'
}

function stateLabel(state: string): string {
  if (['downloading', 'forcedDL'].includes(state)) return 'загружается'
  if (['queuedDL', 'stalledDL', 'metaDL', 'forcedMetaDL'].includes(state)) {
    return 'ожидает источники'
  }
  if (['stoppedDL', 'pausedDL'].includes(state)) return 'приостановлено'
  if (['uploading', 'stalledUP', 'queuedUP', 'stoppedUP', 'pausedUP'].includes(state)) {
    return 'загружено'
  }
  if (state === 'checkingDL' || state === 'checkingUP') return 'проверка файла'
  if (state === 'error' || state === 'missingFiles') return 'ошибка загрузки'
  return state
}

function clearTorrentTimer(): void {
  if (torrentTimer) clearTimeout(torrentTimer)
  torrentTimer = undefined
}

function scheduleTorrentRefresh(): void {
  clearTorrentTimer()
  if (!torrent.value) return
  if (torrent.value.progress >= 1 && torrentFiles.value.length > 0) return
  if (torrentFiles.value.length > 0 && !hasSelectedFile.value) return
  if (
    torrentFiles.value.length > 0
    && ['stoppedDL', 'pausedDL'].includes(torrent.value.state)
  ) return
  torrentTimer = setTimeout(() => void refreshTorrentState(), 5000)
}

function rememberTask(taskId: string): void {
  try {
    localStorage.setItem(taskStorageKey.value, taskId)
  } catch {
    // The active task still works when browser storage is unavailable.
  }
}

function dismissTask(): void {
  try {
    localStorage.setItem(taskStorageKey.value, dismissedTask)
  } catch {
    // Nothing else is required when browser storage is unavailable.
  }
}

async function addSource(sourceId: string): Promise<void> {
  torrentBusy.value = true
  torrentError.value = ''
  try {
    torrent.value = await addTorrent(props.mediaId, props.kind, sourceId)
    rememberTask(torrent.value.id)
    await refreshFiles()
    scheduleTorrentRefresh()
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

async function chooseFileAndStart(file: TorrentFile): Promise<void> {
  if (!torrent.value) return
  torrentBusy.value = true
  torrentError.value = ''
  try {
    torrent.value = await selectTorrentFile(torrent.value.id, file.id)
    if (file.progress < 1) torrent.value = await startTorrent(torrent.value.id)
    await refreshFiles()
    scheduleTorrentRefresh()
  } catch (caught) {
    torrentError.value = friendlyApiError(caught)
  } finally {
    torrentBusy.value = false
  }
}

async function applyTorrentAction(action: 'start' | 'stop'): Promise<void> {
  if (!torrent.value) return
  torrentBusy.value = true
  torrentError.value = ''
  try {
    torrent.value = action === 'start'
      ? await startTorrent(torrent.value.id)
      : await stopTorrent(torrent.value.id)
    scheduleTorrentRefresh()
  } catch (caught) {
    torrentError.value = friendlyApiError(caught)
  } finally {
    torrentBusy.value = false
  }
}

async function saveSelectedVideo(): Promise<void> {
  if (!torrent.value) return
  torrentBusy.value = true
  torrentError.value = ''
  try {
    await saveToLibrary(torrent.value.id, {
      media_id: props.mediaId,
      media_kind: props.kind,
      title: props.title,
      original_title: props.originalTitle,
      poster_url: props.posterUrl,
      backdrop_url: props.backdropUrl,
    })
    librarySaved.value = true
  } catch (caught) {
    torrentError.value = friendlyApiError(caught)
  } finally {
    torrentBusy.value = false
  }
}

async function refreshTorrentState(): Promise<void> {
  if (!torrent.value || torrentBusy.value) {
    scheduleTorrentRefresh()
    return
  }
  try {
    torrent.value = await getTorrent(torrent.value.id)
    if (torrentFiles.value.length === 0) await refreshFiles()
  } catch (caught) {
    torrentError.value = friendlyApiError(caught)
  } finally {
    scheduleTorrentRefresh()
  }
}

function chooseAnotherSource(): void {
  clearTorrentTimer()
  dismissTask()
  torrent.value = null
  torrentFiles.value = []
  torrentError.value = ''
  librarySaved.value = false
}

async function restoreTask(): Promise<void> {
  let taskId: string | null = null
  try {
    taskId = localStorage.getItem(taskStorageKey.value)
  } catch {
    // The server lookup below remains available without browser storage.
  }
  if (taskId === dismissedTask) return
  torrentBusy.value = true
  try {
    torrent.value = taskId
      ? await getTorrent(taskId)
      : await getMediaTorrent(props.mediaId, props.kind)
    rememberTask(torrent.value.id)
    await refreshFiles()
    scheduleTorrentRefresh()
  } catch {
    torrent.value = null
    torrentFiles.value = []
    if (taskId) {
      try {
        torrent.value = await getMediaTorrent(props.mediaId, props.kind)
        rememberTask(torrent.value.id)
        await refreshFiles()
        scheduleTorrentRefresh()
      } catch {
        dismissTask()
      }
    }
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
watch(taskStorageKey, () => {
  clearTorrentTimer()
  torrent.value = null
  torrentFiles.value = []
  torrentError.value = ''
  items.value = []
  searched.value = false
  void restoreTask()
})

onMounted(() => void restoreTask())
onBeforeUnmount(clearTorrentTimer)
</script>

<template>
  <section id="media-sources" class="details-section sources-section">
    <div class="sources-heading">
      <div>
        <p class="eyebrow">Источник просмотра</p>
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

    <div v-if="!torrent && !searched" class="source-intro">
      <div>
        <p class="workflow-step">Шаг 1 из 3</p>
        <h3>Выберите релиз</h3>
        <p>Поиск выполняется вручную через настроенные индексаторы и может занять несколько секунд.</p>
      </div>
      <button class="button primary focus-ring" type="button" @click="loadSources">
        Найти источники
      </button>
    </div>
    <div v-else-if="!torrent && loading" class="source-loading" role="status">Ищем доступные релизы…</div>
    <StatePanel
      v-else-if="!torrent && error"
      title="Поиск источников недоступен"
      :message="error"
      show-retry
      @retry="loadSources"
    />
    <StatePanel
      v-else-if="!torrent && items.length === 0"
      title="Релизы не найдены"
      :message="`По запросу «${query}» настроенные индексаторы ничего не вернули.`"
      show-retry
      @retry="loadSources"
    />
    <div v-else-if="!torrent" class="source-results">
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
          Выбрать релиз
        </button>
      </article>
      <p class="source-stage-note">
        После выбора KADR покажет фильмы или серии внутри релиза. Ничего лишнего автоматически не скачивается.
      </p>
    </div>

    <section v-if="torrent" class="torrent-panel" aria-live="polite">
      <div class="sources-heading">
        <div>
          <p class="workflow-step">Шаг 2 из 3</p>
          <h3>{{ !hasSelectedFile
            ? 'Выберите фильм или серию'
            : torrent.progress >= 1 ? 'Видео готово' : 'Загружаем видео' }}</h3>
          <p class="torrent-release-name">Источник: {{ torrent.name }}</p>
        </div>
        <strong v-if="hasSelectedFile" class="torrent-percent">
          {{ Math.round(torrent.progress * 100) }}%
        </strong>
      </div>
      <template v-if="hasSelectedFile">
        <progress :value="torrent.progress" max="1" />
        <p class="torrent-status-line">
          <strong>{{ stateLabel(torrent.state) }}</strong>
          <span>Скорость: {{ formatSpeed(torrent.download_speed_bytes) }}</span>
          <span>Сиды: {{ torrent.seeds }}</span>
          <span>Пиры: {{ torrent.peers }}</span>
        </p>
      </template>
      <div class="torrent-actions">
        <button class="button secondary focus-ring" type="button" :disabled="torrentBusy" @click="chooseAnotherSource">
          Сменить релиз
        </button>
        <button
          v-if="hasSelectedFile && torrent.can_start"
          class="button primary focus-ring"
          type="button"
          :disabled="torrentBusy"
          @click="applyTorrentAction('start')"
        >
          Продолжить загрузку
        </button>
        <button
          v-if="hasSelectedFile && torrent.can_stop && torrent.progress < 1"
          class="button secondary focus-ring"
          type="button"
          :disabled="torrentBusy"
          @click="applyTorrentAction('stop')"
        >
          Приостановить
        </button>
      </div>
      <div v-if="videoFiles.length && !hasSelectedFile" class="torrent-file-selection">
        <p class="selection-help">
          Нажмите на нужный фильм или эпизод — KADR выберет только этот файл и сразу начнёт загрузку.
        </p>
        <div class="torrent-files">
        <button
          v-for="file in videoFiles"
          :key="file.id"
          class="torrent-file focus-ring"
          :class="{ selected: torrent.selected_file_id === file.id }"
          type="button"
          :disabled="torrentBusy || torrent.selected_file_id === file.id"
          @click="chooseFileAndStart(file)"
        >
          <span>{{ file.name }}</span>
          <small>{{ formatBytes(file.size_bytes) }} · скачано {{ Math.round(file.progress * 100) }}%</small>
          <strong>
            {{ torrent.selected_file_id === file.id
              ? 'Выбрано'
              : file.progress >= 1 ? 'Выбрать для просмотра' : 'Выбрать и скачать' }}
          </strong>
        </button>
        </div>
        <p v-if="skippedFileCount" class="source-stage-note">
          Скрыто сопутствующих файлов: {{ skippedFileCount }}.
        </p>
      </div>
      <div v-else-if="videoFiles.length === 0" class="metadata-wait" role="status">
        <span class="spinner" aria-hidden="true" />
        <div>
          <strong>Получаем список файлов…</strong>
          <p>KADR обновит его автоматически. Обычно это занимает несколько секунд.</p>
        </div>
      </div>
      <div v-if="hasSelectedFile && selectedFile" class="selected-file-summary">
        <div>
          <span>Выбрано для просмотра</span>
          <strong>{{ selectedFile.name }}</strong>
          <small>{{ formatBytes(selectedFile.size_bytes) }}</small>
        </div>
        <details v-if="videoFiles.length > 1" class="change-file-details">
          <summary class="focus-ring">Выбрать другой эпизод</summary>
          <div class="torrent-files compact">
            <button
              v-for="file in videoFiles.filter((item) => item.id !== selectedFile?.id)"
              :key="file.id"
              class="torrent-file focus-ring"
              type="button"
              :disabled="torrentBusy"
              @click="chooseFileAndStart(file)"
            >
              <span>{{ file.name }}</span>
              <small>{{ formatBytes(file.size_bytes) }} · скачано {{ Math.round(file.progress * 100) }}%</small>
              <strong>{{ file.progress >= 1 ? 'Выбрать для просмотра' : 'Выбрать и скачать' }}</strong>
            </button>
          </div>
        </details>
      </div>
      <div v-if="hasSelectedFile && torrent.selected_file_path" class="watch-step">
        <p class="workflow-step">Шаг 3 из 3</p>
        <KadrPlayer
          :task-id="torrent.id"
          :title="title"
          :media-id="mediaId"
          :media-kind="kind"
          :poster-url="posterUrl"
        />
        <div v-if="torrent.progress >= 1" class="library-save-row">
          <p>{{ librarySaved ? 'Видео сохранено в библиотеке.' : 'Сохраните готовый файл для просмотра без повторной загрузки.' }}</p>
          <button
            class="button secondary focus-ring"
            type="button"
            :disabled="torrentBusy || librarySaved"
            @click="saveSelectedVideo"
          >
            {{ librarySaved ? 'Сохранено' : 'Сохранить в библиотеку' }}
          </button>
        </div>
      </div>
    </section>
    <p v-if="torrentError" class="torrent-error" role="alert">{{ torrentError }}</p>
  </section>
</template>
