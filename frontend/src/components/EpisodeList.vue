<script setup lang="ts">
import type { EpisodeSummary, HistoryItem } from '../types/media'
import EpisodeCard from './EpisodeCard.vue'
import StatePanel from './StatePanel.vue'

const props = defineProps<{
  episodes: EpisodeSummary[]
  history?: HistoryItem[]
  completedEpisodeKeys?: string[]
  historyBusyKey?: string
  loading?: boolean
  error?: string
}>()

defineEmits<{
  select: [episode: EpisodeSummary]
  'toggle-watched': [episode: EpisodeSummary]
  retry: []
}>()

function episodeKey(episode: EpisodeSummary): string {
  return `${episode.season_number}:${episode.number}`
}

function episodeHistory(episode: EpisodeSummary): HistoryItem | undefined {
  return props.history?.find((item) => (
    item.season_number === episode.season_number
    && item.episode_number === episode.number
  ))
}

function episodeStatus(episode: EpisodeSummary): 'unwatched' | 'partial' | 'completed' {
  const item = episodeHistory(episode)
  if (props.completedEpisodeKeys?.includes(episodeKey(episode)) || item?.completed) return 'completed'
  return item && item.position_seconds > 0 ? 'partial' : 'unwatched'
}

function handleEpisodeNavigation(event: KeyboardEvent): void {
  if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return
  const target = event.target instanceof HTMLElement ? event.target : null
  const currentCard = target?.closest<HTMLElement>('[data-episode-card]')
  const list = event.currentTarget instanceof HTMLElement ? event.currentTarget : null
  if (!currentCard || !list) return
  const cards = Array.from(list.querySelectorAll<HTMLElement>('[data-episode-card]'))
  const currentIndex = cards.indexOf(currentCard)
  const nextIndex = currentIndex + (event.key === 'ArrowUp' ? -1 : 1)
  const nextCard = cards[nextIndex]
  if (!nextCard) return
  const action = target?.dataset.episodeAction ?? 'play'
  const next = nextCard.querySelector<HTMLElement>(`[data-episode-action="${action}"]`)
    ?? nextCard.querySelector<HTMLElement>('[data-episode-action="play"]')
  if (!next) return
  event.preventDefault()
  event.stopPropagation()
  next.focus({ preventScroll: true })
  next.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}
</script>

<template>
  <div class="episode-list" aria-live="polite" @keydown="handleEpisodeNavigation">
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
        :status="episodeStatus(episode)"
        :position-seconds="episodeHistory(episode)?.position_seconds ?? 0"
        :duration-seconds="episodeHistory(episode)?.duration_seconds ?? 0"
        :history-busy="historyBusyKey === episodeKey(episode)"
        @select="$emit('select', episode)"
        @toggle-watched="$emit('toggle-watched', episode)"
      />
    </div>
    <StatePanel v-else title="Эпизоды не найдены" message="Для этого сезона пока нет данных." />
  </div>
</template>
