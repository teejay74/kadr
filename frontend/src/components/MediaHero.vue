<script setup lang="ts">
import type { MediaDetails } from '../types/media'

defineProps<{ media: MediaDetails }>()
</script>

<template>
  <section class="media-hero">
    <div
      class="details-backdrop"
      :style="media.backdrop_url
        ? { backgroundImage: `linear-gradient(0deg, #101116 0%, rgba(16,17,22,.35) 65%, rgba(16,17,22,.65)), url(${media.backdrop_url})` }
        : {}"
    />
    <div class="details-content">
      <div class="details-poster">
        <img v-if="media.poster_url" :src="media.poster_url" :alt="`Постер: ${media.title}`" />
        <div v-else class="poster-placeholder" aria-hidden="true">K</div>
      </div>
      <div class="details-copy">
        <p class="eyebrow">{{ media.kind === 'movie' ? 'Фильм' : 'Сериал' }}</p>
        <h1>{{ media.title }}</h1>
        <p v-if="media.original_title !== media.title" class="original-title">
          {{ media.original_title }}
        </p>
        <p v-if="media.tagline" class="tagline">{{ media.tagline }}</p>
        <div class="hero-meta">
          <span v-if="media.year">{{ media.year }}</span>
          <span v-if="media.rating">★ {{ media.rating.toFixed(1) }}</span>
          <span v-if="media.runtime_minutes">{{ media.runtime_minutes }} мин.</span>
          <span v-if="media.season_count">{{ media.season_count }} сез.</span>
        </div>
        <div class="genre-list">
          <span v-for="genre in media.genres" :key="genre.id">{{ genre.name }}</span>
        </div>
        <p class="details-overview">{{ media.overview || 'Описание пока не переведено.' }}</p>
        <slot />
      </div>
    </div>
  </section>
</template>
