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
  </div>
</template>
