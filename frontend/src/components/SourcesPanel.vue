<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  addTorrent,
  configureTorrentPrefetch,
  deleteTorrentFile,
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
import type {
  MediaKind,
  SeasonSummary,
  SourceRelease,
  SourceSort,
  TorrentFile,
  TorrentStatus,
} from '../types/media'
import KadrPlayer from './KadrPlayer.vue'
import StatePanel from './StatePanel.vue'

const props = withDefaults(defineProps<{
  mediaId: number
  kind: MediaKind
  title?: string
  originalTitle?: string
  posterUrl?: string | null
  backdropUrl?: string | null
  seasons?: SeasonSummary[]
}>(), { title: '', originalTitle: '', posterUrl: null, backdropUrl: null, seasons: () => [] })
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
const torrentNotice = ref('')
const librarySaved = ref(false)
const prefetchCount = ref(2)
const deleteCandidateId = ref<number | null>(null)
const deletedFileIds = ref<Set<number>>(new Set())
const pendingSeasonDownload = ref<number | null>(null)
const pendingSeasonRequiresMatch = ref(false)
const seasonQueueBusy = ref(false)
let torrentTimer: ReturnType<typeof setTimeout> | undefined
const dismissedTask = 'dismissed'

const videoFiles = computed(() => torrentFiles.value.filter((file) => file.is_video))
const selectedFile = computed(() => videoFiles.value.find(
  (file) => file.id === torrent.value?.selected_file_id,
))
const selectedEpisodeLabel = computed(() => selectedFile.value
  ? describeVideoFile(selectedFile.value.name)
  : '')
const skippedFileCount = computed(() => torrentFiles.value.length - videoFiles.value.length)
const downloadedVideoFiles = computed(() => videoFiles.value.filter(
  (file) => file.progress >= 1 && !deletedFileIds.value.has(file.id),
))
const hasSelectedFile = computed(() => torrent.value?.selected_file_id !== null
  && torrent.value?.selected_file_id !== undefined)
const selectedSeasonNumber = computed(() => selectedFile.value
  ? parseEpisodeIdentity(selectedFile.value.name)?.season ?? null
  : null)
const seasonVideoFiles = computed(() => {
  if (selectedSeasonNumber.value === null) return []
  return videoFiles.value.filter(
    (file) => parseEpisodeIdentity(file.name)?.season === selectedSeasonNumber.value,
  )
})
const seasonDownloadCandidates = computed(() => seasonVideoFiles.value.filter(
  (file) => file.id !== selectedFile.value?.id && file.progress < 1,
))
const followingVideoFiles = computed(() => {
  const selectedIndex = videoFiles.value.findIndex((file) => file.id === selectedFile.value?.id)
  return selectedIndex >= 0 ? videoFiles.value.slice(selectedIndex + 1) : []
})
const prefetchCandidates = computed(() => followingVideoFiles.value.filter(
  (file) => file.progress < 1,
))
const queuedBackgroundFiles = computed(() => videoFiles.value.filter(
  (file) => file.id !== selectedFile.value?.id && file.priority > 0 && file.progress < 1,
))
const effectivePrefetchCount = computed(() => Math.min(
  prefetchCount.value,
  prefetchCandidates.value.length,
))
const hasPendingDownload = computed(() => torrentFiles.value.some(
  (file) => file.priority > 0 && file.progress < 1,
))
const taskStorageKey = computed(() => `kadr:torrent:${props.kind}:${props.mediaId}`)
const knownSeasonNumbers = computed(() => [...new Set(
  props.seasons.map((season) => season.number).filter((number) => number > 0),
)].sort((left, right) => left - right))
const sourceGroups = computed(() => {
  if (props.kind !== 'series') {
    return [{ key: 'all', label: '', sortOrder: 0, items: items.value }]
  }

  const groups = new Map<string, {
    key: string
    label: string
    sortOrder: number
    items: SourceRelease[]
  }>()
  for (const number of knownSeasonNumbers.value) {
    groups.set(`season-${number}`, {
      key: `season-${number}`,
      label: `Сезон ${number}`,
      sortOrder: number,
      items: [],
    })
  }
  for (const item of items.value) {
    const identity = releaseGroupIdentity(item)
    const group = groups.get(identity.key) ?? { ...identity, items: [] }
    group.items.push(item)
    groups.set(identity.key, group)
  }
  return [...groups.values()].sort((left, right) => (
    left.sortOrder - right.sortOrder || left.label.localeCompare(right.label, 'ru')
  ))
})

function formatBytes(bytes: number): string {
  if (bytes <= 0) return 'Размер неизвестен'
  const units = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']
  const unit = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** unit).toFixed(unit > 2 ? 1 : 0)} ${units[unit]}`
}

function formatSpeed(bytes: number): string {
  return bytes > 0 ? `${formatBytes(bytes)}/с` : 'ожидание источников'
}

function releaseSeasonIdentity(title: string): {
  key: string
  label: string
  sortOrder: number
} {
  const range = title.match(/(?:^|[^a-z0-9])s(\d{1,2})\s*[-–—]\s*s?(\d{1,2})(?:[^a-z0-9]|$)/i)
  if (range) {
    const first = Number(range[1])
    const last = Number(range[2])
    return {
      key: `range-${first}-${last}`,
      label: `Сезоны ${first}–${last}`,
      sortOrder: first,
    }
  }

  const season = title.match(/(?:^|[^a-zа-яё0-9])(?:s|season\s*|сезон\s*)(\d{1,2})(?:[^0-9]|$)/i)
    ?? title.match(/(?:^|[^0-9])(\d{1,2})\s*сезон(?:[^а-яёa-z0-9]|$)/i)
  if (season) {
    const number = Number(season[1])
    return { key: `season-${number}`, label: `Сезон ${number}`, sortOrder: number }
  }

  if (/(?:complete|all[ ._-]*seasons?|все[ ._-]*сезоны)/i.test(title)) {
    return { key: 'complete', label: 'Все сезоны', sortOrder: 10_000 }
  }
  return { key: 'other', label: 'Другие релизы', sortOrder: 20_000 }
}

function explicitReleaseSeasonNumbers(item: SourceRelease): number[] {
  if (Array.isArray(item.season_numbers) && item.season_numbers.length) {
    return [...new Set(item.season_numbers)].sort((left, right) => left - right)
  }
  const identity = releaseSeasonIdentity(item.title)
  const singleSeason = identity.key.match(/^season-(\d+)$/)
  if (singleSeason) return [Number(singleSeason[1])]
  const range = identity.key.match(/^range-(\d+)-(\d+)$/)
  if (range) {
    const first = Number(range[1])
    const last = Number(range[2])
    return Array.from({ length: last - first + 1 }, (_, index) => first + index)
  }
  return []
}

function downloadableSeasonNumbers(item: SourceRelease): number[] {
  const explicit = explicitReleaseSeasonNumbers(item)
  if (explicit.length) return explicit
  if (releaseSeasonIdentity(item.title).key === 'complete') return knownSeasonNumbers.value
  return item.season_number == null ? [] : [item.season_number]
}

function releaseGroupIdentity(item: SourceRelease): {
  key: string
  label: string
  sortOrder: number
} {
  if (releaseSeasonIdentity(item.title).key === 'complete') {
    return { key: 'complete', label: 'Все сезоны', sortOrder: 10_000 }
  }
  const seasons = explicitReleaseSeasonNumbers(item)
  if (seasons.length === 1) {
    return {
      key: `season-${seasons[0]}`,
      label: `Сезон ${seasons[0]}`,
      sortOrder: seasons[0],
    }
  }
  if (seasons.length > 1) {
    const consecutive = seasons.every((season, index) => (
      index === 0 || season === seasons[index - 1] + 1
    ))
    const suffix = consecutive
      ? `${seasons[0]}–${seasons[seasons.length - 1]}`
      : seasons.join(', ')
    return {
      key: `seasons-${seasons.join('-')}`,
      label: `Сезоны ${suffix}`,
      sortOrder: seasons[0],
    }
  }
  if (item.season_number != null) {
    return {
      key: `season-${item.season_number}`,
      label: `Сезон ${item.season_number}`,
      sortOrder: item.season_number,
    }
  }
  return releaseSeasonIdentity(item.title)
}

function releaseMatchesRequestedSeason(item: SourceRelease): boolean {
  if (item.season_number == null) return true
  const seasons = explicitReleaseSeasonNumbers(item)
  return seasons.length === 0 || seasons.includes(item.season_number)
}

function deduplicateSources(releases: SourceRelease[]): SourceRelease[] {
  const unique = new Map<string, SourceRelease>()
  for (const release of releases) {
    if (!unique.has(release.id)) unique.set(release.id, release)
  }
  return [...unique.values()]
}

function parseEpisodeIdentity(filename: string): { season: number, episode: number } | null {
  const seasonEpisode = filename.match(/(?:^|[^a-z0-9])s(\d{1,2})e(\d{1,3})(?:[^a-z0-9]|$)/i)
  if (seasonEpisode) {
    return { season: Number(seasonEpisode[1]), episode: Number(seasonEpisode[2]) }
  }

  const alternateEpisode = filename.match(/(?:^|[^0-9])(\d{1,2})x(\d{1,3})(?:[^0-9]|$)/i)
  if (alternateEpisode) {
    return { season: Number(alternateEpisode[1]), episode: Number(alternateEpisode[2]) }
  }

  return null
}

function fileSeasonNumber(filename: string): number | null {
  const episode = parseEpisodeIdentity(filename)
  if (episode) return episode.season
  const directory = filename.match(
    /(?:^|[\\/._ -])(?:season|сезон)[ ._-]?(\d{1,2})(?:[\\/._ -]|$)/i,
  )
  return directory ? Number(directory[1]) : null
}

function describeVideoFile(filename: string): string {
  const identity = parseEpisodeIdentity(filename)
  if (identity) return `Сезон ${identity.season} · Серия ${identity.episode}`

  return props.kind === 'series' ? 'Выбранный эпизод' : 'Выбранный фильм'
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
  if (
    torrent.value.progress >= 1
    && torrentFiles.value.length > 0
    && !hasPendingDownload.value
  ) return
  if (
    torrentFiles.value.length > 0
    && !hasSelectedFile.value
    && pendingSeasonDownload.value === null
  ) return
  if (
    torrentFiles.value.length > 0
    && ['stoppedDL', 'pausedDL'].includes(torrent.value.state)
    && pendingSeasonDownload.value === null
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

async function addSource(
  sourceId: string,
  searchSeasonNumber: number | null = null,
  downloadSeasonNumber: number | null = null,
  requireSeasonMatch = false,
): Promise<void> {
  torrentBusy.value = true
  torrentError.value = ''
  torrentNotice.value = ''
  pendingSeasonDownload.value = downloadSeasonNumber
  pendingSeasonRequiresMatch.value = requireSeasonMatch
  try {
    torrent.value = searchSeasonNumber === null
      ? await addTorrent(props.mediaId, props.kind, sourceId)
      : await addTorrent(props.mediaId, props.kind, sourceId, searchSeasonNumber)
    rememberTask(torrent.value.id)
    await refreshFiles()
    await queuePendingSeason()
    scheduleTorrentRefresh()
  } catch (caught) {
    pendingSeasonDownload.value = null
    pendingSeasonRequiresMatch.value = false
    torrentError.value = friendlyApiError(caught)
  } finally {
    torrentBusy.value = false
  }
}

async function queuePendingSeason(): Promise<void> {
  const seasonNumber = pendingSeasonDownload.value
  if (seasonNumber === null || !torrent.value || seasonQueueBusy.value) return
  const matchingFiles = videoFiles.value.filter(
    (file) => fileSeasonNumber(file.name) === seasonNumber,
  )
  const identifiedFiles = videoFiles.value.filter((file) => fileSeasonNumber(file.name) !== null)
  if (
    videoFiles.value.length
    && !matchingFiles.length
    && (identifiedFiles.length || pendingSeasonRequiresMatch.value)
  ) {
    pendingSeasonDownload.value = null
    pendingSeasonRequiresMatch.value = false
    torrentError.value = `В выбранном релизе не найден сезон ${seasonNumber}. Выберите другой источник.`
    return
  }
  const candidates = (matchingFiles.length ? matchingFiles : videoFiles.value)
    .slice()
    .sort((left, right) => {
      const leftEpisode = parseEpisodeIdentity(left.name)?.episode ?? left.id
      const rightEpisode = parseEpisodeIdentity(right.name)?.episode ?? right.id
      return leftEpisode - rightEpisode || left.id - right.id
    })
  if (!candidates.length) return

  seasonQueueBusy.value = true
  torrentError.value = ''
  try {
    const firstFile = candidates[0]
    torrent.value = await selectTorrentFile(torrent.value.id, firstFile.id)
    const remainingIds = candidates
      .filter((file) => file.id !== firstFile.id && file.progress < 1)
      .map((file) => file.id)
    torrent.value = await configureTorrentPrefetch(torrent.value.id, remainingIds)
    pendingSeasonDownload.value = null
    pendingSeasonRequiresMatch.value = false
    await refreshFiles()
    torrentNotice.value = `Сезон ${seasonNumber} добавлен в загрузку. Эпизодов: ${candidates.length}.`
  } catch (caught) {
    pendingSeasonDownload.value = null
    pendingSeasonRequiresMatch.value = false
    torrentError.value = friendlyApiError(caught)
  } finally {
    seasonQueueBusy.value = false
  }
}

async function refreshFiles(): Promise<void> {
  if (!torrent.value) return
  try {
    const files = await getTorrentFiles(torrent.value.id)
    torrentFiles.value = files.map((file) => deletedFileIds.value.has(file.id)
      ? { ...file, progress: 0, priority: 0 }
      : file)
  } catch (caught) {
    torrentFiles.value = []
    torrentError.value = friendlyApiError(caught)
  }
}

async function chooseFileAndStart(file: TorrentFile): Promise<void> {
  if (!torrent.value) return
  torrentBusy.value = true
  torrentError.value = ''
  torrentNotice.value = ''
  if (deletedFileIds.value.has(file.id)) {
    const nextDeleted = new Set(deletedFileIds.value)
    nextDeleted.delete(file.id)
    deletedFileIds.value = nextDeleted
  }
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

async function deleteDownloadedVideo(file: TorrentFile): Promise<void> {
  if (!torrent.value) return
  if (deleteCandidateId.value !== file.id) {
    deleteCandidateId.value = file.id
    torrentNotice.value = ''
    torrentError.value = ''
    return
  }
  torrentBusy.value = true
  torrentError.value = ''
  torrentNotice.value = ''
  try {
    const result = await deleteTorrentFile(torrent.value.id, file.id)
    deletedFileIds.value = new Set([...deletedFileIds.value, file.id])
    if (result.selected_file_cleared) {
      torrent.value = {
        ...torrent.value,
        selected_file_id: null,
        selected_file_path: null,
        progress: 0,
      }
    }
    await refreshFiles()
    torrentNotice.value = `${describeVideoFile(file.name)} удалён. Освобождено ${formatBytes(result.reclaimed_bytes)}.`
    deleteCandidateId.value = null
    scheduleTorrentRefresh()
  } catch (caught) {
    torrentError.value = friendlyApiError(caught)
  } finally {
    torrentBusy.value = false
  }
}

async function setPrefetch(fileIds: number[], successNotice = ''): Promise<void> {
  if (!torrent.value) return
  torrentBusy.value = true
  torrentError.value = ''
  torrentNotice.value = ''
  try {
    torrent.value = await configureTorrentPrefetch(torrent.value.id, fileIds)
    await refreshFiles()
    torrentNotice.value = successNotice
    scheduleTorrentRefresh()
  } catch (caught) {
    torrentError.value = friendlyApiError(caught)
  } finally {
    torrentBusy.value = false
  }
}

function prefetchNextEpisodes(): void {
  const fileIds = prefetchCandidates.value
    .slice(0, prefetchCount.value)
    .map((file) => file.id)
  void setPrefetch(fileIds)
}

function downloadSelectedSeason(): void {
  if (selectedSeasonNumber.value === null) return
  const fileIds = seasonDownloadCandidates.value.map((file) => file.id)
  void setPrefetch(
    fileIds,
    `Сезон ${selectedSeasonNumber.value} добавлен в загрузку. Эпизодов в очереди: ${fileIds.length}.`,
  )
}

async function applyTorrentAction(action: 'start' | 'stop'): Promise<void> {
  if (!torrent.value) return
  torrentBusy.value = true
  torrentError.value = ''
  torrentNotice.value = ''
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
    await refreshFiles()
    await queuePendingSeason()
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
  torrentNotice.value = ''
  deleteCandidateId.value = null
  deletedFileIds.value = new Set()
  pendingSeasonDownload.value = null
  pendingSeasonRequiresMatch.value = false
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
    if (props.kind !== 'series' || knownSeasonNumbers.value.length === 0) {
      const result = await getSources(props.mediaId, props.kind, sort.value, order.value)
      items.value = result.items
      query.value = result.query
    } else {
      const results = []
      for (let index = 0; index < knownSeasonNumbers.value.length; index += 3) {
        const batch = knownSeasonNumbers.value.slice(index, index + 3)
        results.push(...await Promise.all(batch.map((seasonNumber) => getSources(
          props.mediaId,
          props.kind,
          sort.value,
          order.value,
          seasonNumber,
        ))))
      }
      items.value = deduplicateSources(
        results
          .flatMap((result) => result.items)
          .filter(releaseMatchesRequestedSeason),
      )
      query.value = `${props.title || props.originalTitle} · сезонов: ${knownSeasonNumbers.value.length}`
    }
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
  torrentNotice.value = ''
  deleteCandidateId.value = null
  deletedFileIds.value = new Set()
  pendingSeasonDownload.value = null
  pendingSeasonRequiresMatch.value = false
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
      <details
        v-for="group in sourceGroups"
        :key="group.key"
        class="source-season-group"
        :open="kind !== 'series'"
      >
        <summary v-if="group.label" class="source-season-heading focus-ring">
          <span>{{ group.label }}</span> <small>{{ group.items.length }}</small>
        </summary>
        <p v-if="group.items.length === 0" class="source-season-empty">
          Для этого сезона источники не найдены.
        </p>
        <article v-for="item in group.items" :key="item.id" class="source-release">
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
          <div class="source-actions">
            <button
              class="button source-add focus-ring"
              type="button"
              :disabled="torrentBusy || seasonQueueBusy || torrent !== null"
              @click="addSource(item.id, item.season_number)"
            >
              Выбрать релиз
            </button>
            <button
              v-if="downloadableSeasonNumbers(item).length === 1"
              class="button primary focus-ring"
              type="button"
              :disabled="torrentBusy || seasonQueueBusy || torrent !== null"
              @click="addSource(
                item.id,
                item.season_number,
                downloadableSeasonNumbers(item)[0],
              )"
            >
              Скачать сезон
            </button>
            <details
              v-else-if="downloadableSeasonNumbers(item).length > 1"
              class="source-season-picker"
            >
              <summary class="button primary focus-ring">Скачать сезон</summary>
              <div class="source-season-picker-menu">
                <button
                  v-for="seasonNumber in downloadableSeasonNumbers(item)"
                  :key="seasonNumber"
                  class="button secondary focus-ring"
                  type="button"
                  :disabled="torrentBusy || seasonQueueBusy || torrent !== null"
                  @click="addSource(item.id, item.season_number, seasonNumber, true)"
                >
                  Сезон {{ seasonNumber }}
                </button>
              </div>
            </details>
          </div>
        </article>
      </details>
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
          <b class="selected-episode-label">{{ selectedEpisodeLabel }}</b>
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
      <section v-if="downloadedVideoFiles.length" class="downloaded-files" aria-labelledby="downloaded-files-title">
        <div>
          <h4 id="downloaded-files-title">Скачанные {{ kind === 'series' ? 'серии' : 'видео' }}</h4>
          <p>Удаление освободит место. При необходимости файл можно скачать заново.</p>
        </div>
        <ul>
          <li v-for="file in downloadedVideoFiles" :key="file.id">
            <div>
              <strong>{{ describeVideoFile(file.name) }}</strong>
              <span>{{ file.name }}</span>
              <small>{{ formatBytes(file.size_bytes) }}</small>
            </div>
            <div v-if="deleteCandidateId === file.id" class="delete-confirmation">
              <span>Точно удалить?</span>
              <button
                class="button danger focus-ring"
                type="button"
                :disabled="torrentBusy"
                @click="deleteDownloadedVideo(file)"
              >
                Да, удалить
              </button>
              <button
                class="button secondary focus-ring"
                type="button"
                :disabled="torrentBusy"
                @click="deleteCandidateId = null"
              >
                Отмена
              </button>
            </div>
            <button
              v-else
              class="button secondary focus-ring"
              type="button"
              :disabled="torrentBusy"
              @click="deleteDownloadedVideo(file)"
            >
              Удалить файл
            </button>
          </li>
        </ul>
      </section>
      <section
        v-if="kind === 'series'
          && hasSelectedFile
          && selectedFile
          && (followingVideoFiles.length || selectedSeasonNumber !== null)"
        class="episode-prefetch"
        aria-labelledby="episode-prefetch-title"
      >
        <div>
          <h4 id="episode-prefetch-title">Загрузка серий</h4>
          <p>Текущая серия останется выбранной для просмотра. Остальные загрузятся в фоне.</p>
        </div>
        <div v-if="selectedSeasonNumber !== null" class="season-download-control">
          <button
            class="button primary focus-ring"
            type="button"
            :disabled="torrentBusy || seasonDownloadCandidates.length === 0"
            @click="downloadSelectedSeason"
          >
            Скачать сезон {{ selectedSeasonNumber }} целиком
          </button>
          <small v-if="seasonDownloadCandidates.length">
            Будет загружено эпизодов: {{ seasonDownloadCandidates.length }}
          </small>
          <small v-else>Остальные эпизоды сезона уже загружены или добавлены.</small>
        </div>
        <div v-if="prefetchCandidates.length" class="prefetch-controls next-episodes-control">
          <label>
            <span>Сколько серий</span>
            <select v-model.number="prefetchCount" :disabled="torrentBusy">
              <option v-for="count in [1, 2, 3, 5]" :key="count" :value="count">
                {{ count }}
              </option>
            </select>
          </label>
          <button
            class="button primary focus-ring"
            type="button"
            :disabled="torrentBusy || effectivePrefetchCount === 0"
            @click="prefetchNextEpisodes"
          >
            Скачать следующие {{ effectivePrefetchCount }}
          </button>
        </div>
        <p v-else-if="followingVideoFiles.length" class="prefetch-complete">Все следующие серии уже загружены.</p>
        <div v-if="queuedBackgroundFiles.length" class="prefetch-queue">
          <strong>Загружаются заранее</strong>
          <ul>
            <li v-for="file in queuedBackgroundFiles" :key="file.id">
              <span>{{ describeVideoFile(file.name) }}</span>
              <small>{{ Math.round(file.progress * 100) }}%</small>
            </li>
          </ul>
          <button
            class="button secondary focus-ring"
            type="button"
            :disabled="torrentBusy"
            @click="setPrefetch([])"
          >
            Отменить загрузку следующих серий
          </button>
        </div>
      </section>
      <div v-if="hasSelectedFile && torrent.selected_file_path" class="watch-step">
        <p class="workflow-step">Шаг 3 из 3</p>
        <KadrPlayer
          :key="`${torrent.id}:${torrent.selected_file_id}`"
          :task-id="torrent.id"
          :title="title"
          :selection-label="selectedEpisodeLabel"
          :file-name="selectedFile?.name ?? torrent.selected_file_path"
          :media-id="mediaId"
          :media-kind="kind"
          :poster-url="posterUrl"
          :download-progress="selectedFile?.progress ?? torrent.progress"
          :download-state="torrent.state"
          :download-speed-bytes="torrent.download_speed_bytes"
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
    <p v-if="torrentNotice" class="torrent-notice" role="status">{{ torrentNotice }}</p>
    <p v-if="torrentError" class="torrent-error" role="alert">{{ torrentError }}</p>
  </section>
</template>
