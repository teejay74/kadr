<script setup lang="ts">
import type { EpisodeSummary } from '../types/media'
import MediaStatus, { type MediaAvailabilityStatus } from './MediaStatus.vue'
import PlaybackProgress from './PlaybackProgress.vue'

withDefaults(defineProps<{
  episode: EpisodeSummary
  status?: MediaAvailabilityStatus
  positionSeconds?: number
  durationSeconds?: number
  historyBusy?: boolean
}>(), {
  status: 'unwatched',
  positionSeconds: 0,
  durationSeconds: 0,
  historyBusy: false,
})

defineEmits<{
  select: []
  'toggle-watched': []
}>()
</script>

<template>
  <article class="episode-card" data-episode-card>
    <button
      class="episode-card-main focus-ring"
      type="button"
      data-episode-action="play"
      @click="$emit('select')"
    >
      <div class="episode-image">
        <img v-if="episode.still_url" :src="episode.still_url" :alt="`Кадр: ${episode.name}`" loading="lazy" />
        <div v-else class="episode-placeholder" aria-hidden="true">{{ episode.number }}</div>
        <PlaybackProgress
          :position-seconds="positionSeconds"
          :duration-seconds="durationSeconds || (episode.runtime_minutes ?? 0) * 60"
          :completed="status === 'completed'"
        />
      </div>
      <div class="episode-copy">
        <div class="episode-title-row">
          <div>
            <span>Серия {{ episode.number }}</span>
            <h3>{{ episode.name || `Серия ${episode.number}` }}</h3>
          </div>
          <span v-if="episode.runtime_minutes" class="episode-runtime">
            {{ episode.runtime_minutes }} мин.
          </span>
        </div>
        <p>{{ episode.overview || 'Описание эпизода пока не переведено.' }}</p>
        <MediaStatus :status="status" />
      </div>
    </button>
    <button
      class="episode-watched-toggle focus-ring"
      type="button"
      data-episode-action="toggle"
      :disabled="historyBusy"
      :aria-label="status === 'completed'
        ? `Отметить серию ${episode.number} непросмотренной`
        : `Отметить серию ${episode.number} просмотренной`"
      @click="$emit('toggle-watched')"
    >
      <span aria-hidden="true">{{ status === 'completed' ? '↶' : '✓' }}</span>
      {{ status === 'completed' ? 'Не просмотрено' : 'Просмотрено' }}
    </button>
  </article>
</template>
