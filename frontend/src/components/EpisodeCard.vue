<script setup lang="ts">
import type { EpisodeSummary } from '../types/media'
import MediaStatus, { type MediaAvailabilityStatus } from './MediaStatus.vue'
import PlaybackProgress from './PlaybackProgress.vue'

withDefaults(defineProps<{
  episode: EpisodeSummary
  status?: MediaAvailabilityStatus
  positionSeconds?: number
  durationSeconds?: number
}>(), {
  status: 'unwatched',
  positionSeconds: 0,
  durationSeconds: 0,
})

defineEmits<{ select: [] }>()
</script>

<template>
  <button class="episode-card focus-ring" type="button" @click="$emit('select')">
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
</template>
