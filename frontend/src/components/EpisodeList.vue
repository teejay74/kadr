<script setup lang="ts">
import type { EpisodeSummary } from '../types/media'
import EpisodeCard from './EpisodeCard.vue'
import StatePanel from './StatePanel.vue'

defineProps<{
  episodes: EpisodeSummary[]
  loading?: boolean
  error?: string
}>()

defineEmits<{
  select: [episode: EpisodeSummary]
  retry: []
}>()
</script>

<template>
  <div class="episode-list" aria-live="polite">
    <div v-if="loading" class="episode-skeletons" aria-label="Загрузка эпизодов">
      <div v-for="index in 3" :key="index" class="episode-skeleton" />
    </div>
    <StatePanel
      v-else-if="error"
      title="Эпизоды недоступны"
      :message="error"
      show-retry
      @retry="$emit('retry')"
    />
    <div v-else-if="episodes.length" class="episode-items">
      <EpisodeCard
        v-for="episode in episodes"
        :key="episode.id"
        :episode="episode"
        @select="$emit('select', episode)"
      />
    </div>
    <StatePanel v-else title="Эпизоды не найдены" message="Для этого сезона пока нет данных." />
  </div>
</template>
