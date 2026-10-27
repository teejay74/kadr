<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type {
  EpisodeMatchFile,
  EpisodeMatchIdentity,
  EpisodeMatchReport,
  EpisodeMatchSelection,
} from '../types/media'

const props = withDefaults(defineProps<{
  report: EpisodeMatchReport
  busy?: boolean
  error?: string
}>(), {
  busy: false,
  error: '',
})

const emit = defineEmits<{
  close: []
  confirm: [mappings: EpisodeMatchSelection[]]
}>()

const selected = ref<Record<number, string[]>>({})

function identityKey(episode: EpisodeMatchIdentity): string {
  return `${episode.season_number}:${episode.episode_number}`
}

function options(file: EpisodeMatchFile): EpisodeMatchIdentity[] {
  const unique = new Map<string, EpisodeMatchIdentity>()
  for (const episode of [...file.episodes, ...file.alternatives]) {
    unique.set(identityKey(episode), episode)
  }
  return [...unique.values()].sort((left, right) => (
    left.season_number - right.season_number
    || left.episode_number - right.episode_number
  ))
}

function resetSelections(): void {
  selected.value = Object.fromEntries(props.report.files
    .filter((file) => !file.confirmed && !file.unsafe)
    .map((file) => [file.file_id, file.episodes.map(identityKey)]))
}

function toggle(fileId: number, key: string, checked: boolean): void {
  const current = new Set(selected.value[fileId] ?? [])
  if (checked) current.add(key)
  else current.delete(key)
  selected.value = { ...selected.value, [fileId]: [...current] }
}

function onToggle(fileId: number, key: string, event: Event): void {
  const input = event.target
  if (input instanceof HTMLInputElement) toggle(fileId, key, input.checked)
}

const mappings = computed<EpisodeMatchSelection[]>(() => props.report.files.flatMap((file) => {
  if (file.confirmed || file.unsafe) return []
  const keys = new Set(selected.value[file.file_id] ?? [])
  const episodes = options(file).filter((episode) => keys.has(identityKey(episode)))
  return episodes.length ? [{ file_id: file.file_id, episodes }] : []
}))

function submit(): void {
  if (mappings.value.length) emit('confirm', mappings.value)
}

watch(() => props.report, resetSelections, { immediate: true, deep: true })
</script>

<template>
  <div class="episode-match-backdrop" @click.self="emit('close')">
    <section
      class="episode-match-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="episode-match-title"
    >
      <header>
        <div>
          <p class="eyebrow">Episode Matcher</p>
          <h2 id="episode-match-title">Проверьте соответствия серий</h2>
        </div>
        <button class="button secondary focus-ring" type="button" :disabled="busy" @click="emit('close')">
          Закрыть
        </button>
      </header>
      <p class="episode-match-intro">
        Точные однозначные совпадения уже сохранены. Для остальных файлов отметьте одну или несколько серий.
        Если один файл содержит две серии, KADR сохранит обе связи, но не сможет перейти к началу второй без временных границ.
      </p>
      <p v-if="!report.metadata_available" class="episode-match-warning">
        TMDB временно недоступен: автоматические привязки отключены.
      </p>
      <div class="episode-match-list">
        <article v-for="file in report.files" :key="file.file_id" class="episode-match-file">
          <div class="episode-match-file-heading">
            <strong>{{ file.file_path }}</strong>
            <span :class="`confidence-${file.confidence}`">{{ file.confidence }}</span>
          </div>
          <p v-for="reason in file.reasons" :key="reason">{{ reason }}</p>
          <p v-if="file.confirmed" class="episode-match-saved">
            Сохранено: {{ file.episodes.map((episode) => `S${episode.season_number}E${episode.episode_number}`).join(', ') }}
          </p>
          <p v-else-if="file.unsafe" class="episode-match-warning">
            Этот путь небезопасен и не может быть подтверждён.
          </p>
          <fieldset v-else-if="options(file).length">
            <legend>Эпизоды в файле</legend>
            <label v-for="episode in options(file)" :key="identityKey(episode)">
              <input
                type="checkbox"
                :checked="selected[file.file_id]?.includes(identityKey(episode))"
                :disabled="busy"
                @change="onToggle(
                  file.file_id,
                  identityKey(episode),
                  $event,
                )"
              >
              <span>
                S{{ episode.season_number }}E{{ episode.episode_number }}
                <template v-if="episode.name"> · {{ episode.name }}</template>
              </span>
            </label>
          </fieldset>
          <p v-else>Matcher не нашёл безопасного варианта. Выберите файл вручную в списке источника.</p>
        </article>
      </div>
      <p v-if="error" class="torrent-error" role="alert">{{ error }}</p>
      <footer>
        <button class="button secondary focus-ring" type="button" :disabled="busy" @click="emit('close')">
          Решить позже
        </button>
        <button
          class="button primary focus-ring"
          type="button"
          :disabled="busy || mappings.length === 0"
          @click="submit"
        >
          {{ busy ? 'Сохраняем…' : 'Сохранить соответствия' }}
        </button>
      </footer>
    </section>
  </div>
</template>
