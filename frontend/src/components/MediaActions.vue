<script setup lang="ts">
import PlayButton from './PlayButton.vue'

withDefaults(defineProps<{
  playLabel?: string
  favorite: boolean
  favoriteBusy?: boolean
  trailerUrl?: string | null
}>(), {
  playLabel: 'Смотреть',
  favoriteBusy: false,
  trailerUrl: null,
})

defineEmits<{
  play: []
  toggleFavorite: []
  changeSource: []
}>()
</script>

<template>
  <div class="action-row media-actions">
    <PlayButton :label="playLabel" @play="$emit('play')" />
    <button
      class="button secondary focus-ring"
      type="button"
      :disabled="favoriteBusy"
      @click="$emit('toggleFavorite')"
    >
      {{ favorite ? 'В избранном' : 'В избранное' }}
    </button>
    <a
      v-if="trailerUrl"
      class="button secondary focus-ring"
      :href="trailerUrl"
      target="_blank"
      rel="noopener"
    >
      Трейлер ↗
    </a>
    <details class="media-actions-menu">
      <summary class="button secondary focus-ring" aria-label="Другие действия">⋯</summary>
      <div>
        <button class="button secondary focus-ring" type="button" @click="$emit('changeSource')">
          Другой источник
        </button>
      </div>
    </details>
  </div>
</template>
