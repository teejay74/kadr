<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  positionSeconds?: number
  durationSeconds?: number
  completed?: boolean
}>(), {
  positionSeconds: 0,
  durationSeconds: 0,
  completed: false,
})

const progress = computed(() => {
  if (props.completed) return 1
  if (props.durationSeconds <= 0) return 0
  return Math.min(Math.max(props.positionSeconds / props.durationSeconds, 0), 1)
})
</script>

<template>
  <div
    v-if="progress > 0"
    class="playback-progress"
    role="progressbar"
    aria-label="Прогресс просмотра"
    aria-valuemin="0"
    aria-valuemax="100"
    :aria-valuenow="Math.round(progress * 100)"
  >
    <span :style="{ width: `${progress * 100}%` }" />
  </div>
</template>
