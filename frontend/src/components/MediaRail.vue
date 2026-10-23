<script setup lang="ts">
import MediaCard from './MediaCard.vue'
import type { MediaCardData } from '../types/media'

defineProps<{ title: string; items: MediaCardData[]; moreTo: string }>()
</script>

<template>
  <section class="rail-section">
    <div class="section-heading">
      <h2>{{ title }}</h2>
      <RouterLink class="text-link focus-ring" :to="moreTo">Смотреть все →</RouterLink>
    </div>
    <div class="media-rail">
      <MediaCard v-for="media in items" :key="`${media.kind}-${media.id}`" :media="media" />
    </div>
  </section>
</template>
