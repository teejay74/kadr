<script setup lang="ts">
import { computed } from 'vue'

export type MediaAvailabilityStatus =
  | 'unwatched'
  | 'partial'
  | 'completed'
  | 'downloaded'
  | 'downloading'
  | 'error'

const props = withDefaults(defineProps<{
  status?: MediaAvailabilityStatus
}>(), { status: 'unwatched' })

const label = computed(() => ({
  unwatched: 'Смотреть',
  partial: 'Продолжить',
  completed: 'Просмотрено',
  downloaded: 'Скачано',
  downloading: 'Загружается',
  error: 'Источник недоступен',
})[props.status])
</script>

<template>
  <span class="media-status" :class="`status-${status}`">
    <span aria-hidden="true">{{ status === 'completed' ? '✓' : status === 'error' ? '!' : '▶' }}</span>
    {{ label }}
  </span>
</template>
