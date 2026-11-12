<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { ApiError, friendlyApiError, getTorrentFiles, saveEpisodeToLibrary } from '../services/api'
import type { EpisodeSummary, MediaDetails } from '../types/media'

const props = defineProps<{
  taskId: string
  fileId: number
  initialProgress: number
  media: MediaDetails
  episode: EpisodeSummary | null
}>()

const complete = ref(props.initialProgress >= 1)
const busy = ref(false)
const saved = ref(false)
const error = ref('')
let timer: ReturnType<typeof setTimeout> | undefined
let disposed = false

function scheduleProgressCheck(): void {
  if (!disposed && !complete.value) timer = setTimeout(() => void checkProgress(), 15_000)
}

async function checkProgress(): Promise<void> {
  try {
    const files = await getTorrentFiles(props.taskId)
    complete.value = files.some((file) => file.id === props.fileId && file.is_video && file.progress >= 1)
    error.value = ''
  } catch (caught) {
    error.value = friendlyApiError(caught)
  } finally {
    scheduleProgressCheck()
  }
}

async function save(): Promise<void> {
  if (!complete.value || busy.value || saved.value) return
  busy.value = true
  error.value = ''
  try {
    const media = props.media
    await saveEpisodeToLibrary(props.taskId, {
      media_id: media.id,
      media_kind: media.kind,
      title: media.title,
      original_title: media.original_title,
      poster_url: media.poster_url,
      backdrop_url: media.backdrop_url,
    }, props.episode, props.fileId)
    saved.value = true
  } catch (caught) {
    error.value = caught instanceof ApiError && caught.status === 504
      ? 'Сервер ещё может сохранять файл. Проверьте «Библиотеку» перед повторной попыткой.'
      : friendlyApiError(caught)
  } finally {
    busy.value = false
  }
}

onMounted(scheduleProgressCheck)
onBeforeUnmount(() => {
  disposed = true
  clearTimeout(timer)
})
</script>

<template>
  <div class="library-save-row">
    <p v-if="saved" role="status">Видео сохранено в библиотеке.</p>
    <p v-else-if="busy" role="status">Сохранение большого файла может занять несколько минут.</p>
    <p v-else-if="!complete">Сохранение доступно после полной загрузки видео.</p>
    <button class="button secondary focus-ring" type="button" :disabled="!complete || busy || saved" @click="save">
      {{ saved ? 'Сохранено' : busy ? 'Сохраняем…' : 'Сохранить в библиотеку' }}
    </button>
    <p v-if="error" class="torrent-error" role="alert">{{ error }}</p>
  </div>
</template>
