<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  friendlyApiError,
  getCompatiblePlayback,
  getHistoryItem,
  getStreamReadiness,
  startCompatiblePlayback,
  updateHistory,
} from '../services/api'
import type {
  EpisodeSummary,
  MediaKind,
  PlaybackMode,
  PlaybackPreparation,
} from '../types/media'

const props = withDefaults(defineProps<{
  taskId: string
  title: string
  selectionLabel?: string
  fileName?: string
  mediaId?: number
  mediaKind?: MediaKind
  posterUrl?: string | null
  fileId?: number
  episode?: EpisodeSummary | null
  downloadProgress?: number
  downloadState?: string
  downloadSpeedBytes?: number
  directStreamUrl?: string
  autoActivate?: boolean
  initialResumeSeconds?: number
}>(), {
  selectionLabel: '',
  fileName: '',
  mediaId: 0,
  mediaKind: 'movie',
  posterUrl: null,
  fileId: -1,
  episode: null,
  downloadProgress: 0,
  downloadState: '',
  downloadSpeedBytes: 0,
  directStreamUrl: '',
  autoActivate: false,
  initialResumeSeconds: -1,
})

const active = ref(false)
const waiting = ref(false)
const streamReady = ref(false)
const bufferProgress = ref(0)
const error = ref('')
const video = ref<HTMLVideoElement | null>(null)
const resumeAt = ref(0)
const streamAttempt = ref(0)
const compatible = ref<PlaybackPreparation | null>(null)
const compatibleMode = ref<PlaybackMode>('compatible')
const usingCompatible = ref(false)
let lastSavedSecond = -1
let playbackEnded = false
let readinessTimer: ReturnType<typeof setTimeout> | undefined
let compatibilityTimer: ReturnType<typeof setTimeout> | undefined
let preparationId = 0
let readinessAttempts = 0
const maxReadinessAttempts = 12

const streamUrl = computed(() => {
  const base = usingCompatible.value
    ? compatible.value?.stream_url
      ?? `/api/v1/torrents/${encodeURIComponent(props.taskId)}/compatible/stream`
    : props.directStreamUrl
      || `/api/v1/torrents/${encodeURIComponent(props.taskId)}/stream`
  if (streamAttempt.value === 0) return base
  const separator = base.includes('?') ? '&' : '?'
  return `${base}${separator}attempt=${streamAttempt.value}`
})
const storageKey = computed(() => {
  if (props.episode) {
    return `kadr:playback:${props.mediaId}:s${props.episode.season_number}:e${props.episode.number}`
  }
  return props.fileId >= 0
    ? `kadr:playback:${props.taskId}:f${props.fileId}`
    : `kadr:playback:${props.taskId}`
})
const downloadPercent = computed(() => Math.round(props.downloadProgress * 100))
const downloadStateLabel = computed(() => {
  if (props.downloadProgress >= 1) return 'файл загружен полностью'
  if (['downloading', 'forcedDL'].includes(props.downloadState)) return 'эпизод загружается'
  if (['queuedDL', 'stalledDL', 'metaDL', 'forcedMetaDL'].includes(props.downloadState)) {
    return 'ожидаем данные от источников'
  }
  if (['stoppedDL', 'pausedDL'].includes(props.downloadState)) return 'загрузка приостановлена'
  if (props.downloadState === 'error' || props.downloadState === 'missingFiles') {
    return 'ошибка загрузки'
  }
  return 'проверяем состояние загрузки'
})
const downloadStatus = computed(() => {
  const speed = props.downloadSpeedBytes > 0
    ? ` · ${formatBytes(props.downloadSpeedBytes)}/с`
    : ''
  return `Скачано ${downloadPercent.value}% · ${downloadStateLabel.value}${speed}`
})

function readSavedPosition(): number {
  try {
    const value = Number.parseFloat(localStorage.getItem(storageKey.value) ?? '0')
    return Number.isFinite(value) && value >= 5 ? value : 0
  } catch {
    return 0
  }
}

function formatTime(seconds: number): string {
  const total = Math.floor(seconds)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const remainder = total % 60
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
    : `${minutes}:${String(remainder).padStart(2, '0')}`
}

function formatBytes(bytes: number): string {
  const units = ['Б', 'КБ', 'МБ', 'ГБ']
  const unit = Math.min(Math.floor(Math.log(Math.max(bytes, 1)) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** unit).toFixed(unit > 1 ? 1 : 0)} ${units[unit]}`
}

async function startVideoElement(): Promise<void> {
  await nextTick()
  const element = video.value
  if (!element) return
  element.focus()
  try {
    await element.play()
  } catch {
    waiting.value = false
    error.value = 'Буфер готов, но браузер заблокировал автоматический запуск. Нажмите ▶ в плеере.'
  }
}

async function activate(): Promise<void> {
  error.value = ''
  waiting.value = true
  playbackEnded = false
  readinessAttempts = 0
  resumeAt.value = Math.max(readSavedPosition(), props.initialResumeSeconds)
  if (props.initialResumeSeconds < 0) {
    try {
      const history = props.mediaId > 0
        ? await getHistoryItem(props.mediaId, props.mediaKind, props.episode)
        : null
      if (history && !history.completed) resumeAt.value = Math.max(resumeAt.value, history.position_seconds)
    } catch {
      // Browser-local resume remains available when the API is unavailable.
    }
  }
  active.value = true
  streamReady.value = false
  bufferProgress.value = 0
  usingCompatible.value = false
  preparationId += 1
  if (props.directStreamUrl) {
    await prepareStream(preparationId)
    return
  }
  try {
    for (const mode of ['compatible', 'audio_only'] as const) {
      const existing = await getCompatiblePlayback(props.taskId, mode)
      if (existing.state === 'ready') {
        compatibleMode.value = mode
        await handleCompatibility(existing)
        return
      }
    }
  } catch {
    // Direct Play remains available when no compatible artifact exists yet.
  }
  await prepareStream(preparationId)
}

async function prepareCompatible(): Promise<void> {
  await startPreparation('compatible')
}

async function prepareAudioOnly(): Promise<void> {
  await startPreparation('audio_only')
}

async function startPreparation(mode: PlaybackMode): Promise<void> {
  preparationId += 1
  if (readinessTimer) clearTimeout(readinessTimer)
  if (compatibilityTimer) clearTimeout(compatibilityTimer)
  active.value = true
  streamReady.value = false
  waiting.value = false
  error.value = ''
  compatibleMode.value = mode
  try {
    await handleCompatibility(await startCompatiblePlayback(props.taskId, mode))
  } catch (reason) {
    error.value = friendlyApiError(reason)
  }
}

async function pollCompatibility(): Promise<void> {
  try {
    await handleCompatibility(await getCompatiblePlayback(props.taskId, compatibleMode.value))
  } catch (reason) {
    error.value = friendlyApiError(reason)
  }
}

async function handleCompatibility(status: PlaybackPreparation): Promise<void> {
  compatible.value = status
  if (status.state === 'failed') {
    error.value = status.message ?? 'FFmpeg не смог подготовить совместимую версию.'
    return
  }
  if (status.state !== 'ready') {
    compatibilityTimer = setTimeout(() => void pollCompatibility(), 3000)
    return
  }
  usingCompatible.value = true
  streamReady.value = true
  waiting.value = true
  streamAttempt.value += 1
  await startVideoElement()
}

async function prepareStream(id = ++preparationId): Promise<void> {
  error.value = ''
  waiting.value = true
  if (readinessTimer) clearTimeout(readinessTimer)
  if (compatibilityTimer) clearTimeout(compatibilityTimer)
  if (props.directStreamUrl) {
    bufferProgress.value = 1
    streamReady.value = true
    await startVideoElement()
    return
  }
  try {
    const readiness = await getStreamReadiness(props.taskId)
    if (!active.value || id !== preparationId) return
    bufferProgress.value = readiness.buffer_progress
    if (!readiness.ready) {
      readinessAttempts += 1
      if (readinessAttempts >= maxReadinessAttempts) {
        waiting.value = false
        error.value = 'Источник не подготовил начальный буфер за минуту. Повторите попытку или выберите другой источник.'
        return
      }
      readinessTimer = setTimeout(() => void prepareStream(id), 5000)
      return
    }
    streamReady.value = true
    await startVideoElement()
  } catch {
    if (!active.value || id !== preparationId) return
    waiting.value = false
    error.value = 'Не удалось проверить готовность видеопотока. Нажмите «Повторить».'
  }
}

function onLoadedMetadata(): void {
  waiting.value = false
  const duration = video.value?.duration ?? 0
  if (resumeAt.value >= Math.max(duration - 10, 5)) resumeAt.value = 0
}

function continuePlayback(): void {
  if (video.value && resumeAt.value > 0) video.value.currentTime = resumeAt.value
  resumeAt.value = 0
}

function restartPlayback(): void {
  try {
    localStorage.removeItem(storageKey.value)
  } catch {
    // Playback remains usable when browser storage is unavailable.
  }
  if (video.value) video.value.currentTime = 0
  resumeAt.value = 0
}

function savePosition(): void {
  if (playbackEnded) return
  const current = Math.floor(video.value?.currentTime ?? 0)
  if (current < 5 || current === lastSavedSecond) return
  lastSavedSecond = current
  try {
    localStorage.setItem(storageKey.value, String(current))
  } catch {
    // Playback remains usable when browser storage is unavailable.
  }
  if (props.mediaId <= 0) return
  void updateHistory(props.mediaId, {
    media_kind: props.mediaKind,
    title: props.title,
    poster_url: props.posterUrl,
    position_seconds: current,
    duration_seconds: Math.floor(video.value?.duration ?? 0),
    completed: false,
    ...(props.episode ? {
      season_number: props.episode.season_number,
      episode_number: props.episode.number,
      catalog_episode_id: props.episode.id,
    } : {}),
  }).catch(() => undefined)
}

function onTimeUpdate(): void {
  const current = Math.floor(video.value?.currentTime ?? 0)
  if (current - lastSavedSecond >= 5) savePosition()
}

function onEnded(): void {
  playbackEnded = true
  try {
    localStorage.removeItem(storageKey.value)
  } catch {
    // Playback remains usable when browser storage is unavailable.
  }
  lastSavedSecond = -1
  if (props.mediaId <= 0) return
  void updateHistory(props.mediaId, {
    media_kind: props.mediaKind,
    title: props.title,
    poster_url: props.posterUrl,
    position_seconds: 0,
    duration_seconds: Math.floor(video.value?.duration ?? 0),
    completed: true,
    ...(props.episode ? {
      season_number: props.episode.season_number,
      episode_number: props.episode.number,
      catalog_episode_id: props.episode.id,
    } : {}),
  }).catch(() => undefined)
}

function onPlaying(): void {
  playbackEnded = false
  waiting.value = false
}

function stopPlayback(): void {
  preparationId += 1
  if (readinessTimer) clearTimeout(readinessTimer)
  if (compatibilityTimer) clearTimeout(compatibilityTimer)
  savePosition()
  const element = video.value
  if (element) {
    element.pause()
    element.removeAttribute('src')
    element.load()
  }
  active.value = false
  streamReady.value = false
  waiting.value = false
  resumeAt.value = 0
}

function onPlaybackError(): void {
  waiting.value = false
  const code = video.value?.error?.code ?? 0
  if (code === 2) {
    error.value = 'Сетевая ошибка видеопотока. Нажмите «Повторить» после подготовки загрузки.'
  } else if (code === 3) {
    error.value = 'Браузер не смог декодировать видео или аудио. Подготовьте совместимую версию.'
  } else if (code === 4) {
    error.value = 'Формат или кодеки не поддерживаются браузером. Подготовьте совместимую версию.'
  } else {
    error.value = 'Не удалось открыть видеопоток. Проверьте состояние загрузки и попробуйте снова.'
  }
}

async function retryPlayback(): Promise<void> {
  error.value = ''
  waiting.value = true
  readinessAttempts = 0
  if (!streamReady.value) {
    await prepareStream()
    return
  }
  streamAttempt.value += 1
  await nextTick()
  const element = video.value
  if (!element) return
  element.load()
  try {
    await element.play()
  } catch {
    onPlaybackError()
  }
}

onMounted(() => {
  if (props.autoActivate) void activate()
})
onBeforeUnmount(stopPlayback)
</script>

<template>
  <section class="player-card" aria-label="Видеоплеер">
    <div v-if="!active" class="player-launch">
      <div class="player-launch-copy">
        <h3>Смотреть выбранное видео</h3>
        <p v-if="directStreamUrl">Видео сохранено локально и доступно без повторной загрузки.</p>
        <p v-else>Просмотр можно начать до завершения загрузки — KADR сам подготовит начальный буфер.</p>
        <strong v-if="selectionLabel" class="player-selection-label">{{ selectionLabel }}</strong>
        <small>{{ fileName || title }}</small>
        <span class="player-download-status" :class="{ complete: downloadProgress >= 1 }">
          {{ downloadStatus }}
        </span>
      </div>
      <div class="player-launch-actions">
        <button class="button primary focus-ring" type="button" @click="activate">
          Начать просмотр
        </button>
        <details class="compatibility-help">
          <summary>Если нет изображения или звука</summary>
          <p>Если изображение уже есть, быстрый режим сохранит видео и преобразует только звук.</p>
          <div class="compatibility-actions">
            <button class="button secondary focus-ring" type="button" @click="prepareAudioOnly">
              Быстро исправить звук
            </button>
            <button class="button secondary focus-ring" type="button" @click="prepareCompatible">
              Полная совместимая версия
            </button>
          </div>
        </details>
      </div>
    </div>
    <div v-else class="player-active">
      <div class="player-toolbar">
        <div class="player-toolbar-title">
          <strong>{{ selectionLabel || title }}</strong>
          <small v-if="selectionLabel">{{ fileName || title }}</small>
          <span class="player-download-status" :class="{ complete: downloadProgress >= 1 }">
            {{ downloadStatus }}
          </span>
        </div>
        <button class="button secondary focus-ring" type="button" @click="stopPlayback">
          Закрыть плеер
        </button>
      </div>
      <div class="video-frame">
        <video
          v-if="streamReady"
          ref="video"
          :src="streamUrl"
          controls
          playsinline
          preload="metadata"
          tabindex="0"
          @loadedmetadata="onLoadedMetadata"
          @waiting="waiting = true"
          @playing="onPlaying"
          @pause="savePosition"
          @timeupdate="onTimeUpdate"
          @ended="onEnded"
          @error="onPlaybackError"
        >
          Ваш браузер не поддерживает воспроизведение видео.
        </video>
        <div v-if="waiting" class="player-status" role="status">
          <strong>
            {{ streamReady
              ? 'Буфер готов — открываем видео…'
              : `Подготавливаем начальный буфер… ${Math.round(bufferProgress * 100)}%` }}
          </strong>
          <span>{{ downloadStatus }}</span>
          <small v-if="!streamReady">
            KADR автоматически проверяет готовность потока каждые 5 секунд.
          </small>
        </div>
        <p
          v-else-if="compatible && ['probing', 'processing'].includes(compatible.state)"
          class="player-status"
          role="status"
        >
          FFmpeg: {{ compatible.state === 'probing'
            ? 'анализ'
            : compatible.mode === 'audio_only' ? 'исправляем звук' : 'подготовка' }}…
          {{ Math.round(compatible.progress * 100) }}%
        </p>
      </div>
      <div v-if="resumeAt" class="resume-prompt" role="status">
        <span>Продолжить с {{ formatTime(resumeAt) }}?</span>
        <button class="button primary focus-ring" type="button" @click="continuePlayback">Продолжить</button>
        <button class="button secondary focus-ring" type="button" @click="restartPlayback">Сначала</button>
      </div>
      <div v-if="error" class="player-error">
        <p class="torrent-error" role="alert">{{ error }}</p>
        <button class="button secondary focus-ring" type="button" @click="retryPlayback">
          Повторить
        </button>
        <button class="button primary focus-ring" type="button" @click="prepareCompatible">
          Полная совместимая версия
        </button>
        <button class="button secondary focus-ring" type="button" @click="prepareAudioOnly">
          Быстро исправить звук
        </button>
      </div>
    </div>
  </section>
</template>
