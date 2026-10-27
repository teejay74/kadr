<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import StatePanel from '../components/StatePanel.vue'
import {
  deleteTorrentFile,
  friendlyApiError,
  getTorrentFiles,
  getTorrents,
  startTorrent,
  stopTorrent,
} from '../services/api'
import type { TorrentFile, TorrentStatus } from '../types/media'

const tasks = ref<TorrentStatus[]>([])
const files = ref<Record<string, TorrentFile[]>>({})
const loading = ref(true)
const error = ref('')
const busyTaskId = ref<string | null>(null)
const fileLoadingTaskId = ref<string | null>(null)
const deleteCandidate = ref<{ taskId: string, fileId: number } | null>(null)
let refreshTimer: ReturnType<typeof setTimeout> | undefined

const activeCount = computed(() => tasks.value.filter((task) => task.can_stop && task.progress < 1).length)

function formatBytes(bytes: number): string {
  if (bytes <= 0) return '0 Б'
  const units = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']
  const unit = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** unit).toFixed(unit > 2 ? 1 : 0)} ${units[unit]}`
}

function stateLabel(state: string): string {
  if (['downloading', 'forcedDL'].includes(state)) return 'Загружается'
  if (['queuedDL', 'stalledDL', 'metaDL', 'forcedMetaDL'].includes(state)) return 'Ожидает источники'
  if (['stoppedDL', 'pausedDL'].includes(state)) return 'Приостановлено'
  if (['uploading', 'stalledUP', 'queuedUP', 'stoppedUP', 'pausedUP'].includes(state)) return 'Загружено'
  if (state === 'unavailable') return 'Нет в qBittorrent'
  if (state === 'error' || state === 'missingFiles') return 'Ошибка'
  return state
}

function scheduleRefresh(): void {
  if (refreshTimer) clearTimeout(refreshTimer)
  if (activeCount.value > 0) refreshTimer = setTimeout(() => void load(false), 10_000)
}

async function load(showLoader = true): Promise<void> {
  if (showLoader) loading.value = true
  error.value = ''
  try {
    tasks.value = await getTorrents()
  } catch (caught) {
    error.value = friendlyApiError(caught)
  } finally {
    loading.value = false
    scheduleRefresh()
  }
}

async function loadFiles(taskId: string): Promise<void> {
  if (files.value[taskId] || fileLoadingTaskId.value) return
  fileLoadingTaskId.value = taskId
  error.value = ''
  try {
    files.value = { ...files.value, [taskId]: await getTorrentFiles(taskId) }
  } catch (caught) {
    error.value = friendlyApiError(caught)
  } finally {
    fileLoadingTaskId.value = null
  }
}

async function applyAction(task: TorrentStatus, action: 'start' | 'stop'): Promise<void> {
  busyTaskId.value = task.id
  error.value = ''
  try {
    const updated = action === 'start' ? await startTorrent(task.id) : await stopTorrent(task.id)
    tasks.value = tasks.value.map((item) => item.id === updated.id ? updated : item)
  } catch (caught) {
    error.value = friendlyApiError(caught)
  } finally {
    busyTaskId.value = null
    scheduleRefresh()
  }
}

async function removeFile(taskId: string, file: TorrentFile): Promise<void> {
  if (deleteCandidate.value?.taskId !== taskId || deleteCandidate.value.fileId !== file.id) {
    deleteCandidate.value = { taskId, fileId: file.id }
    return
  }
  busyTaskId.value = taskId
  error.value = ''
  try {
    await deleteTorrentFile(taskId, file.id)
    files.value = {
      ...files.value,
      [taskId]: (files.value[taskId] ?? []).filter((item) => item.id !== file.id),
    }
    await load(false)
  } catch (caught) {
    error.value = friendlyApiError(caught)
  } finally {
    deleteCandidate.value = null
    busyTaskId.value = null
  }
}

onMounted(() => void load())
onBeforeUnmount(() => {
  if (refreshTimer) clearTimeout(refreshTimer)
})
</script>

<template>
  <div class="page-container downloads-page">
    <div class="page-title-row">
      <div>
        <p class="eyebrow">Техническое управление</p>
        <h1>Загрузки</h1>
      </div>
      <p>{{ tasks.length }} задач · активных {{ activeCount }}</p>
    </div>
    <StatePanel v-if="loading" title="Загружаем задачи" message="Получаем состояние KADR и qBittorrent." />
    <StatePanel v-else-if="error && !tasks.length" title="Загрузки недоступны" :message="error" show-retry @retry="load" />
    <p v-else-if="error" class="torrent-error" role="alert">{{ error }}</p>
    <section v-if="!loading && tasks.length" class="download-task-list">
      <article v-for="task in tasks" :key="task.id" class="download-task-card">
        <header>
          <div>
            <p class="eyebrow">{{ task.media_kind === 'movie' ? 'Фильм' : 'Сериал' }}</p>
            <h2>{{ task.name }}</h2>
            <RouterLink class="text-link" :to="`/${task.media_kind === 'movie' ? 'movies' : 'series'}/${task.media_id}`">
              Открыть карточку
            </RouterLink>
          </div>
          <strong class="download-state">{{ stateLabel(task.state) }}</strong>
        </header>
        <progress :value="task.progress" max="1" />
        <dl class="download-metrics">
          <div><dt>Готово</dt><dd>{{ Math.round(task.progress * 100) }}%</dd></div>
          <div><dt>Скорость</dt><dd>{{ formatBytes(task.download_speed_bytes) }}/с</dd></div>
          <div><dt>Сиды</dt><dd>{{ task.seeds }}</dd></div>
          <div><dt>Пиры</dt><dd>{{ task.peers }}</dd></div>
          <div><dt>Объём</dt><dd>{{ formatBytes(task.total_size_bytes) }}</dd></div>
        </dl>
        <p v-if="task.selected_file_path" class="download-selected-file">
          Выбрано: {{ task.selected_file_path }}
        </p>
        <div class="torrent-actions">
          <button
            v-if="task.can_start"
            class="button primary focus-ring"
            type="button"
            :disabled="busyTaskId === task.id"
            @click="applyAction(task, 'start')"
          >
            Продолжить
          </button>
          <button
            v-if="task.can_stop && task.progress < 1"
            class="button secondary focus-ring"
            type="button"
            :disabled="busyTaskId === task.id"
            @click="applyAction(task, 'stop')"
          >
            Приостановить
          </button>
          <button
            class="button secondary focus-ring"
            type="button"
            :disabled="fileLoadingTaskId !== null || task.state === 'unavailable'"
            @click="loadFiles(task.id)"
          >
            {{ files[task.id] ? 'Файлы загружены' : 'Показать файлы' }}
          </button>
        </div>
        <ul v-if="files[task.id]" class="download-file-list">
          <li v-for="file in files[task.id]" :key="file.id">
            <div>
              <strong>{{ file.name }}</strong>
              <small>{{ formatBytes(file.size_bytes) }} · {{ Math.round(file.progress * 100) }}%</small>
            </div>
            <button
              v-if="file.is_video && file.progress >= 1"
              class="button danger focus-ring"
              type="button"
              :disabled="busyTaskId === task.id"
              @click="removeFile(task.id, file)"
            >
              {{ deleteCandidate?.taskId === task.id && deleteCandidate.fileId === file.id
                ? 'Подтвердить удаление'
                : 'Удалить файл' }}
            </button>
          </li>
        </ul>
      </article>
    </section>
    <StatePanel
      v-else-if="!loading && !error"
      title="Загрузок пока нет"
      message="Выбранные для просмотра источники появятся здесь автоматически."
    />
  </div>
</template>
