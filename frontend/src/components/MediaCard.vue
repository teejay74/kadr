<script setup lang="ts">
import PosterImage from './PosterImage.vue'
import type { MediaCardData } from '../types/media'

defineProps<{ media: MediaCardData }>()
</script>

<template>
  <RouterLink
    class="media-card focus-ring"
    :to="`/${media.kind === 'movie' ? 'movies' : 'series'}/${media.id}`"
  >
    <div class="poster-frame">
      <PosterImage :src="media.poster_url" :alt="`Постер: ${media.title}`" loading="lazy" />
      <span v-if="media.rating > 0" class="rating-badge">★ {{ media.rating.toFixed(1) }}</span>
    </div>
    <div class="media-card-copy">
      <h3>{{ media.title }}</h3>
      <p>{{ media.year ?? 'Год не указан' }} · {{ media.kind === 'movie' ? 'Фильм' : 'Сериал' }}</p>
    </div>
  </RouterLink>
</template>
