<script setup lang="ts">
import { computed } from 'vue'

import type { SourceRelease } from '../types/media'

const props = withDefaults(defineProps<{
  title: string
  items: SourceRelease[]
  loading?: boolean
  busySourceId?: string | null
  error?: string
}>(), {
  loading: false,
  busySourceId: null,
  error: '',
})

const emit = defineEmits<{
  close: []
  retry: []
  select: [source: SourceRelease]
}>()

function formatBytes(bytes: number): string {
  if (bytes <= 0) return 'Размер неизвестен'
  const units = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']
  const unit = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** unit).toFixed(unit > 2 ? 1 : 0)} ${units[unit]}`
}

function qualityScore(source: SourceRelease): number {
  const resolution = { '2160p': 25, '1080p': 30, '720p': 15 }[source.resolution ?? ''] ?? 0
  const availability = source.seeders == null ? 0 : Math.min(source.seeders, 20)
  const release = source.source === 'WEB-DL' ? 8 : source.source === 'BluRay' ? 6 : 0
  return resolution + availability + release
}

const recommendedId = computed(() => [...props.items]
  .sort((left, right) => qualityScore(right) - qualityScore(left))[0]?.id ?? null)

function releaseLabel(source: SourceRelease): string {
  return [source.source, source.release_type, source.codec].filter(Boolean).join(' · ')
    || 'Тип релиза не указан'
}
</script>

<template>
  <div class="source-selector-backdrop" @click.self="emit('close')">
    <section
      class="source-selector-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="source-selector-title"
    >
      <header>
        <div>
          <p class="eyebrow">Источник просмотра</p>
          <h2 id="source-selector-title">Выберите источник</h2>
          <p>{{ title }}</p>
        </div>
        <button class="button secondary focus-ring" type="button" data-tv-back-action :disabled="busySourceId !== null" @click="emit('close')">
          Закрыть
        </button>
      </header>

      <div v-if="loading" class="source-selector-state" aria-live="polite">
        <span class="spinner" aria-hidden="true" />
        <p>Ищем доступные варианты…</p>
      </div>
      <div v-else-if="error" class="source-selector-state">
        <p class="torrent-error" role="alert">{{ error }}</p>
        <button class="button secondary focus-ring" type="button" @click="emit('retry')">
          Повторить поиск
        </button>
      </div>
      <div v-else-if="items.length" class="source-selector-list">
        <article v-for="source in items" :key="source.id" class="source-selector-item">
          <div class="source-selector-copy">
            <div class="source-selector-heading">
              <strong>{{ source.resolution || 'Качество не указано' }}</strong>
              <span v-if="source.id === recommendedId" class="source-recommended">
                Рекомендуемый для проверки
              </span>
            </div>
            <p>{{ releaseLabel(source) }}</p>
            <dl>
              <div><dt>Размер</dt><dd>{{ formatBytes(source.size_bytes) }}</dd></div>
              <div><dt>Язык / озвучка</dt><dd>{{ source.language || source.audio || 'Не указано' }}</dd></div>
              <div><dt>Сиды</dt><dd>{{ source.seeders ?? 'Нет данных' }}</dd></div>
            </dl>
            <details>
              <summary>Технические подробности</summary>
              <p>{{ source.title }}</p>
              <small>Индексатор: {{ source.indexer }}</small>
            </details>
          </div>
          <button
            class="button primary focus-ring"
            type="button"
            :disabled="busySourceId !== null"
            @click="emit('select', source)"
          >
            {{ busySourceId === source.id ? 'Подготавливаем…' : 'Выбрать' }}
          </button>
        </article>
        <p class="source-recommendation-note">
          Рекомендация учитывает качество и доступность, но количество сидов не гарантирует воспроизведение.
        </p>
      </div>
      <div v-else class="source-selector-state">
        <p>Подходящие источники не найдены.</p>
        <button class="button secondary focus-ring" type="button" @click="emit('retry')">
          Повторить поиск
        </button>
      </div>
    </section>
  </div>
</template>
