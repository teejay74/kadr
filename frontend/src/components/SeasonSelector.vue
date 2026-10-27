<script setup lang="ts">
import type { SeasonSummary } from '../types/media'

defineProps<{
  seasons: SeasonSummary[]
  modelValue: number
  disabled?: boolean
}>()

const emit = defineEmits<{ 'update:modelValue': [value: number] }>()

function episodeCountLabel(count: number): string {
  const lastTwo = count % 100
  const last = count % 10
  if (lastTwo >= 11 && lastTwo <= 14) return `${count} серий`
  if (last === 1) return `${count} серия`
  if (last >= 2 && last <= 4) return `${count} серии`
  return `${count} серий`
}

function update(value: string): void {
  emit('update:modelValue', Number(value))
}
</script>

<template>
  <label class="season-selector">
    <span>Сезон</span>
    <select
      class="focus-ring"
      :value="modelValue"
      :disabled="disabled"
      @change="update(($event.target as HTMLSelectElement).value)"
    >
      <option v-for="season in seasons" :key="season.id" :value="season.number">
        {{ season.name || `Сезон ${season.number}` }} · {{ episodeCountLabel(season.episode_count) }}
      </option>
    </select>
  </label>
</template>
