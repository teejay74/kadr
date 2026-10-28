<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  cancelCompatiblePlayback,
  friendlyApiError,
  getCompatiblePlayback,
  getHistoryItem,
  getPlaybackTracks,
  getStreamReadiness,
  preparePlaybackSubtitle,
  savePlaybackTrackPreferences,
  startCompatiblePlayback,
  updateHistory,
} from '../services/api'
import type {
  EpisodeSummary,
  MediaKind,
  PlaybackMode,
  PlaybackPreparation,
  PlaybackTrack,
  PlaybackTrackList,
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
  libraryItemId?: string
  profileKey?: string
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
  libraryItemId: '',
  profileKey: 'default',
  autoActivate: false,
  initialResumeSeconds: -1,
})

const emit = defineEmits<{
  'near-end': []
  'ended': []
}>()

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
const compatibleTrackId = ref('')
const usingCompatible = ref(false)
const currentDownloadProgress = ref(props.downloadProgress)
const currentDownloadState = ref(props.downloadState)
const currentDownloadSpeedBytes = ref(props.downloadSpeedBytes)
const trackList = ref<PlaybackTrackList | null>(null)
const tracksOpen = ref(false)
const tracksLoading = ref(false)
const tracksError = ref('')
const trackStatus = ref('')
const pendingCompatibleAudioTrackId = ref('')
const pendingSubtitleTrackId = ref('')
const externalSubtitleUrl = ref('')
const externalSubtitleTrackId = ref('')
const trackSwitchPosition = ref(0)
let lastSavedSecond = -1
let playbackEnded = false
let nearEndEmitted = false
let readinessTimer: ReturnType<typeof setTimeout> | undefined
let compatibilityTimer: ReturnType<typeof setTimeout> | undefined
let preparationId = 0
let readinessAttempts = 0
const maxReadinessAttempts = 12

interface NativeAudioTrack {
  id: string
  language: string
  label: string
  enabled: boolean
}

interface NativeAudioTrackList {
  length: number
  [index: number]: NativeAudioTrack
}

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
const downloadPercent = computed(() => Math.round(currentDownloadProgress.value * 100))
const downloadStateLabel = computed(() => {
  if (currentDownloadProgress.value >= 1) return 'файл загружен полностью'
  if (['downloading', 'forcedDL'].includes(currentDownloadState.value)) return 'эпизод загружается'
  if (['queuedDL', 'stalledDL', 'metaDL', 'forcedMetaDL'].includes(currentDownloadState.value)) {
    return 'ожидаем данные от источников'
  }
  if (['stoppedDL', 'pausedDL'].includes(currentDownloadState.value)) return 'загрузка приостановлена'
  if (currentDownloadState.value === 'error' || currentDownloadState.value === 'missingFiles') {
    return 'ошибка загрузки'
  }
  return 'проверяем состояние загрузки'
})
const downloadStatus = computed(() => {
  const speed = currentDownloadSpeedBytes.value > 0
    ? ` · ${formatBytes(currentDownloadSpeedBytes.value)}/с`
    : ''
  return `Скачано ${downloadPercent.value}% · ${downloadStateLabel.value}${speed}`
})
const selectedAudioTrack = computed(() => trackList.value?.audio_tracks.find(
  (track) => track.id === trackList.value?.selected_audio_track_id,
) ?? null)
const selectedSubtitleTrack = computed(() => trackList.value?.subtitle_tracks.find(
  (track) => track.id === trackList.value?.selected_subtitle_track_id,
) ?? null)

function languageLabel(language: string | null): string {
  const labels: Record<string, string> = {
    en: 'Английский',
    ru: 'Русский',
    uk: 'Украинский',
    de: 'Немецкий',
    fr: 'Французский',
    es: 'Испанский',
    it: 'Итальянский',
    ja: 'Японский',
    ko: 'Корейский',
    zh: 'Китайский',
  }
  return language ? labels[language] ?? language.toUpperCase() : 'Язык не указан'
}

function trackLabel(track: PlaybackTrack): string {
  const parts = [languageLabel(track.language)]
  if (track.title) parts.push(track.title)
  if (track.channels) parts.push(`${track.channels} каналов`)
  parts.push(track.codec.toUpperCase())
  if (track.is_default) parts.push('по умолчанию')
  if (track.is_forced) parts.push('форсированные')
  return parts.join(' · ')
}

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

async function toggleTracks(): Promise<void> {
  tracksOpen.value = !tracksOpen.value
  if (!tracksOpen.value || trackList.value || tracksLoading.value) return
  tracksLoading.value = true
  tracksError.value = ''
  try {
    trackList.value = await getPlaybackTracks(
      props.taskId,
      props.libraryItemId,
      props.profileKey,
    )
    applyResolvedTracks()
  } catch (reason) {
    tracksError.value = friendlyApiError(reason)
  } finally {
    tracksLoading.value = false
  }
}

async function selectAudioTrack(trackId: string): Promise<void> {
  if (!trackList.value) return
  await saveTrackSelection(trackId, trackList.value.selected_subtitle_track_id, trackList.value.subtitles_enabled)
}

async function selectSubtitleTrack(trackId: string | null): Promise<void> {
  if (!trackList.value) return
  await saveTrackSelection(
    trackList.value.selected_audio_track_id,
    trackId ?? trackList.value.selected_subtitle_track_id,
    trackId !== null,
  )
}

async function prepareSelectedSubtitle(): Promise<void> {
  if (!pendingSubtitleTrackId.value || !video.value) return
  tracksLoading.value = true
  tracksError.value = ''
  trackSwitchPosition.value = video.value.currentTime
  try {
    const prepared = await preparePlaybackSubtitle(
      props.taskId,
      props.libraryItemId,
      pendingSubtitleTrackId.value,
    )
    externalSubtitleUrl.value = prepared.stream_url
    externalSubtitleTrackId.value = prepared.track_id
    pendingSubtitleTrackId.value = ''
    trackStatus.value = 'Субтитры подготовлены и подключены.'
    await nextTick()
    video.value?.load()
  } catch (reason) {
    tracksError.value = friendlyApiError(reason)
  } finally {
    tracksLoading.value = false
  }
}

async function saveTrackSelection(
  audioTrackId: string | null,
  subtitleTrackId: string | null,
  subtitlesEnabled: boolean,
): Promise<void> {
  tracksLoading.value = true
  tracksError.value = ''
  trackStatus.value = ''
  try {
    trackList.value = await savePlaybackTrackPreferences(
      props.taskId,
      props.libraryItemId,
      {
        profile_key: props.profileKey,
        audio_track_id: audioTrackId,
        subtitle_track_id: subtitleTrackId,
        subtitles_enabled: subtitlesEnabled,
      },
    )
    if (
      !subtitlesEnabled
      || externalSubtitleTrackId.value !== selectedSubtitleTrack.value?.id
    ) {
      externalSubtitleUrl.value = ''
      externalSubtitleTrackId.value = ''
    }
    const audioApplied = selectedAudioTrack.value
      ? applyNativeAudioTrack(selectedAudioTrack.value)
      : true
    const subtitleApplied = !subtitlesEnabled
      || (Boolean(externalSubtitleUrl.value)
        && externalSubtitleTrackId.value === selectedSubtitleTrack.value?.id)
      || applyNativeSubtitleTrack(selectedSubtitleTrack.value)
    const applied = audioApplied && subtitleApplied
    pendingCompatibleAudioTrackId.value = audioApplied || !selectedAudioTrack.value || Boolean(props.libraryItemId)
      ? ''
      : selectedAudioTrack.value.id
    pendingSubtitleTrackId.value = !subtitlesEnabled
      || !selectedSubtitleTrack.value
      || selectedSubtitleTrack.value.delivery !== 'external_webvtt'
      || subtitleApplied
      ? ''
      : selectedSubtitleTrack.value.id
    trackStatus.value = applied
      ? 'Выбор применён без перезапуска потока.'
      : 'Выбор сохранён. Этот браузер не умеет переключить дорожку внутри текущего файла.'
  } catch (reason) {
    tracksError.value = friendlyApiError(reason)
  } finally {
    tracksLoading.value = false
  }
}

async function prepareSelectedAudioTrack(): Promise<void> {
  if (!pendingCompatibleAudioTrackId.value) return
  trackSwitchPosition.value = video.value?.currentTime ?? 0
  compatibleTrackId.value = pendingCompatibleAudioTrackId.value
  preparationId += 1
  if (readinessTimer) clearTimeout(readinessTimer)
  if (compatibilityTimer) clearTimeout(compatibilityTimer)
  streamReady.value = false
  waiting.value = false
  error.value = ''
  compatibleMode.value = 'audio_track'
  try {
    await handleCompatibility(
      await startCompatiblePlayback(
        props.taskId,
        'audio_track',
        compatibleTrackId.value,
      ),
    )
  } catch (reason) {
    error.value = friendlyApiError(reason)
  }
}

function applyResolvedTracks(): boolean {
  if (!trackList.value || !video.value) return false
  const audioApplied = selectedAudioTrack.value
    ? applyNativeAudioTrack(selectedAudioTrack.value)
    : true
  const subtitleApplied = applyNativeSubtitleTrack(
    trackList.value.subtitles_enabled ? selectedSubtitleTrack.value : null,
  )
  return audioApplied && subtitleApplied
}

function applyNativeAudioTrack(track: PlaybackTrack): boolean {
  const element = video.value as (HTMLVideoElement & { audioTracks?: NativeAudioTrackList }) | null
  const nativeTracks = element?.audioTracks
  if (!nativeTracks || nativeTracks.length === 0) return false
  const match = findNativeTrack(nativeTracks, track)
  if (!match) return false
  try {
    for (let index = 0; index < nativeTracks.length; index += 1) {
      nativeTracks[index].enabled = nativeTracks[index] === match
    }
    return true
  } catch {
    return false
  }
}

function findNativeTrack(
  tracks: NativeAudioTrackList,
  requested: PlaybackTrack,
): NativeAudioTrack | null {
  let best: NativeAudioTrack | null = null
  let bestScore = 0
  for (let index = 0; index < tracks.length; index += 1) {
    const candidate = tracks[index]
    let score = 0
    if (requested.language && candidate.language.toLowerCase() === requested.language) score += 4
    if (
      requested.title
      && candidate.label.toLocaleLowerCase().includes(requested.title.toLocaleLowerCase())
    ) score += 3
    if (score > bestScore) {
      best = candidate
      bestScore = score
    }
  }
  if (best) return best
  return tracks.length === 1 ? tracks[0] : null
}

function applyNativeSubtitleTrack(track: PlaybackTrack | null): boolean {
  const nativeTracks = video.value?.textTracks
  if (!nativeTracks) return track === null
  let matched = track === null
  for (let index = 0; index < nativeTracks.length; index += 1) {
    const candidate = nativeTracks[index]
    const languageMatches = Boolean(
      track?.language && candidate.language.toLowerCase() === track.language,
    )
    const titleMatches = Boolean(
      track?.title
      && candidate.label.toLocaleLowerCase().includes(track.title.toLocaleLowerCase()),
    )
    const selected = track !== null && (languageMatches || titleMatches)
    candidate.mode = selected ? 'showing' : 'disabled'
    matched = matched || selected
  }
  return matched
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
  nearEndEmitted = false
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
  trackList.value = null
  tracksOpen.value = false
  tracksError.value = ''
  trackStatus.value = ''
  pendingCompatibleAudioTrackId.value = ''
  pendingSubtitleTrackId.value = ''
  externalSubtitleUrl.value = ''
  externalSubtitleTrackId.value = ''
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
  compatibleTrackId.value = ''
  try {
    await handleCompatibility(await startCompatiblePlayback(props.taskId, mode))
  } catch (reason) {
    error.value = friendlyApiError(reason)
  }
}

async function pollCompatibility(): Promise<void> {
  try {
    await handleCompatibility(await getCompatiblePlayback(
      props.taskId,
      compatibleMode.value,
      compatibleTrackId.value,
    ))
  } catch (reason) {
    error.value = friendlyApiError(reason)
  }
}

async function cancelQueuedPreparation(): Promise<void> {
  if (compatible.value?.state !== 'queued') return
  if (compatibilityTimer) clearTimeout(compatibilityTimer)
  try {
    compatible.value = await cancelCompatiblePlayback(
      props.taskId,
      compatibleMode.value,
      compatibleTrackId.value,
    )
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
    currentDownloadProgress.value = readiness.file_progress
    if (readiness.download_state) currentDownloadState.value = readiness.download_state
    currentDownloadSpeedBytes.value = readiness.download_speed_bytes
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
  if (trackList.value) applyResolvedTracks()
  const duration = video.value?.duration ?? 0
  if (video.value && trackSwitchPosition.value > 0) {
    video.value.currentTime = Number.isFinite(duration) && duration > 1
      ? Math.min(trackSwitchPosition.value, duration - 1)
      : trackSwitchPosition.value
    trackSwitchPosition.value = 0
    resumeAt.value = 0
    void video.value.play().catch(() => undefined)
  }
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
  const duration = video.value?.duration ?? 0
  if (
    props.episode
    && !nearEndEmitted
    && Number.isFinite(duration)
    && duration >= 180
    && duration - current <= 90
  ) {
    nearEndEmitted = true
    emit('near-end')
  }
}

function onEnded(): void {
  playbackEnded = true
  try {
    localStorage.removeItem(storageKey.value)
  } catch {
    // Playback remains usable when browser storage is unavailable.
  }
  lastSavedSecond = -1
  emit('ended')
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
        <span class="player-download-status" :class="{ complete: currentDownloadProgress >= 1 }">
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
          <span class="player-download-status" :class="{ complete: currentDownloadProgress >= 1 }">
            {{ downloadStatus }}
          </span>
        </div>
        <div class="player-toolbar-actions">
          <button
            class="button secondary focus-ring"
            type="button"
            aria-controls="kadr-track-menu"
            :aria-expanded="tracksOpen"
            @click="toggleTracks"
          >
            Аудио и субтитры
          </button>
          <button class="button secondary focus-ring" type="button" @click="stopPlayback">
            Закрыть плеер
          </button>
        </div>
      </div>
      <section v-if="tracksOpen" id="kadr-track-menu" class="track-menu" aria-label="Аудио и субтитры">
        <p v-if="tracksLoading" role="status">Определяем дорожки файла…</p>
        <p v-else-if="tracksError" class="torrent-error" role="alert">{{ tracksError }}</p>
        <template v-else-if="trackList">
          <fieldset class="track-group">
            <legend>Аудиодорожка</legend>
            <p v-if="trackList.audio_tracks.length === 0">Аудиодорожки не найдены.</p>
            <label v-for="track in trackList.audio_tracks" :key="track.id" class="track-option">
              <input
                type="radio"
                name="kadr-audio-track"
                :value="track.id"
                :checked="track.id === trackList.selected_audio_track_id"
                :disabled="tracksLoading"
                @change="selectAudioTrack(track.id)"
              >
              <span>{{ trackLabel(track) }}</span>
            </label>
          </fieldset>
          <fieldset class="track-group">
            <legend>Субтитры</legend>
            <label class="track-option">
              <input
                type="radio"
                name="kadr-subtitle-track"
                value="off"
                :checked="!trackList.subtitles_enabled"
                :disabled="tracksLoading"
                @change="selectSubtitleTrack(null)"
              >
              <span>Выключены</span>
            </label>
            <label v-for="track in trackList.subtitle_tracks" :key="track.id" class="track-option">
              <input
                type="radio"
                name="kadr-subtitle-track"
                :value="track.id"
                :checked="trackList.subtitles_enabled && track.id === trackList.selected_subtitle_track_id"
                :disabled="tracksLoading || track.delivery === 'unsupported'"
                @change="selectSubtitleTrack(track.id)"
              >
              <span>{{ trackLabel(track) }}</span>
            </label>
          </fieldset>
          <small v-if="trackStatus" class="track-status" role="status">{{ trackStatus }}</small>
          <button
            v-if="pendingCompatibleAudioTrackId"
            class="button primary focus-ring"
            type="button"
            :disabled="tracksLoading"
            @click="prepareSelectedAudioTrack"
          >
            Подготовить выбранную аудиодорожку
          </button>
          <button
            v-if="pendingSubtitleTrackId"
            class="button primary focus-ring"
            type="button"
            :disabled="tracksLoading"
            @click="prepareSelectedSubtitle"
          >
            Подготовить выбранные субтитры
          </button>
        </template>
      </section>
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
          <track
            v-if="externalSubtitleUrl"
            kind="subtitles"
            :src="externalSubtitleUrl"
            :srclang="selectedSubtitleTrack?.language || 'und'"
            :label="selectedSubtitleTrack?.title || languageLabel(selectedSubtitleTrack?.language ?? null)"
            default
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
        <div
          v-else-if="compatible && ['queued', 'probing', 'processing'].includes(compatible.state)"
          class="player-status"
          role="status"
        >
          <span v-if="compatible.state === 'queued'">
            В очереди на подготовку<span v-if="compatible.queue_position">, позиция {{ compatible.queue_position }}</span>.
          </span>
          <span v-else>
            FFmpeg: {{ compatible.state === 'probing'
              ? 'анализ'
              : compatible.mode === 'audio_only'
                ? 'исправляем звук'
                : compatible.mode === 'audio_track'
                  ? 'готовим выбранную аудиодорожку'
                  : 'подготовка' }}…
            {{ Math.round(compatible.progress * 100) }}%
          </span>
          <button
            v-if="compatible.state === 'queued'"
            class="button secondary focus-ring"
            type="button"
            @click="cancelQueuedPreparation"
          >
            Убрать из очереди
          </button>
        </div>
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
