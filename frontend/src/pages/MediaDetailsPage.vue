<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import StatePanel from '../components/StatePanel.vue'
import { friendlyApiError, getMediaDetails } from '../services/api'
import type { MediaDetails, MediaKind } from '../types/media'

const route = useRoute()
const kind = computed(() => route.meta.kind as MediaKind)
const media = ref<MediaDetails | null>(null)
const loading = ref(true)
const error = ref('')

async function loadDetails(): Promise<void> {
  const id = Number(route.params.id)
  if (!Number.isInteger(id) || id <= 0) {
    error.value = 'Некорректный идентификатор.'
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  try {
    media.value = await getMediaDetails(kind.value, id)
  } catch (caught) {
    error.value = friendlyApiError(caught)
  } finally {
    loading.value = false
  }
}

watch(() => route.fullPath, loadDetails, { immediate: true })
</script>

<template>
  <div v-if="loading" class="page-container"><div class="hero-skeleton" /></div>
  <div v-else-if="error" class="page-container centered-state">
    <StatePanel
      title="Карточка недоступна"
      :message="error"
      show-retry
      @retry="loadDetails"
    />
  </div>
  <article v-else-if="media" class="details-page">
    <div class="details-backdrop" :style="media.backdrop_url ? { backgroundImage: `linear-gradient(0deg, #101116 0%, rgba(16,17,22,.35) 65%, rgba(16,17,22,.65)), url(${media.backdrop_url})` } : {}" />
    <div class="details-content">
      <div class="details-poster"><img v-if="media.poster_url" :src="media.poster_url" :alt="`Постер: ${media.title}`" /><div v-else class="poster-placeholder">K</div></div>
      <div class="details-copy">
        <p class="eyebrow">{{ media.kind === 'movie' ? 'Фильм' : 'Сериал' }}</p>
        <h1>{{ media.title }}</h1>
        <p v-if="media.original_title !== media.title" class="original-title">{{ media.original_title }}</p>
        <p v-if="media.tagline" class="tagline">{{ media.tagline }}</p>
        <div class="hero-meta">
          <span v-if="media.year">{{ media.year }}</span><span v-if="media.rating">★ {{ media.rating.toFixed(1) }}</span><span v-if="media.runtime_minutes">{{ media.runtime_minutes }} мин.</span><span v-if="media.season_count">{{ media.season_count }} сез.</span>
        </div>
        <div class="genre-list"><span v-for="genre in media.genres" :key="genre.id">{{ genre.name }}</span></div>
        <p class="details-overview">{{ media.overview || 'Описание пока не переведено.' }}</p>
        <div class="action-row">
          <button class="button primary" type="button" disabled title="Воспроизведение появится на этапе 5">Смотреть · этап 5</button>
          <a v-if="media.trailer_url" class="button secondary focus-ring" :href="media.trailer_url" target="_blank" rel="noopener">Трейлер ↗</a>
        </div>
      </div>
    </div>

    <section v-if="media.cast.length" class="details-section">
      <h2>В ролях</h2>
      <div class="cast-grid">
        <div v-for="person in media.cast" :key="person.id" class="cast-card">
          <img v-if="person.profile_url" :src="person.profile_url" :alt="person.name" loading="lazy" />
          <div v-else class="avatar-placeholder">{{ person.name.slice(0, 1) }}</div>
          <strong>{{ person.name }}</strong><span>{{ person.character }}</span>
        </div>
      </div>
    </section>

    <section v-if="media.kind === 'series' && media.seasons.length" class="details-section">
      <h2>Сезоны</h2>
      <div class="season-list">
        <div v-for="season in media.seasons" :key="season.id" class="season-row">
          <span class="season-number">{{ season.number }}</span>
          <div><strong>{{ season.name }}</strong><p>{{ season.episode_count }} эпизодов<span v-if="season.air_date"> · {{ season.air_date.slice(0, 4) }}</span></p></div>
        </div>
      </div>
    </section>
  </article>
</template>
