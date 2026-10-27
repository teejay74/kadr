<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { NextEpisodeResolution } from '../types/media'

const props = defineProps<{
  result: NextEpisodeResolution | null
  loading: boolean
  autoPlay: boolean
}>()

const emit = defineEmits<{
  play: []
  'choose-source': []
  close: []
  'update:autoPlay': [value: boolean]
}>()

const countdown = ref(5)
let timer: ReturnType<typeof setInterval> | undefined

function stopCountdown(): void {
  if (timer) clearInterval(timer)
  timer = undefined
}

function startCountdown(): void {
  stopCountdown()
  countdown.value = 5
  if (!props.autoPlay || !props.result?.playback) return
  if (!['ready', 'buffering'].includes(props.result.status)) return
  timer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) {
      stopCountdown()
      emit('play')
    }
  }, 1000)
}

watch(
  () => [props.autoPlay, props.result?.status, props.loading],
  startCountdown,
)
onMounted(startCountdown)
onBeforeUnmount(stopCountdown)
</script>

<template>
  <div class="next-episode-backdrop" role="dialog" aria-modal="true" aria-labelledby="next-episode-title">
    <section class="next-episode-dialog">
      <p class="eyebrow">Продолжить просмотр</p>
      <h2 id="next-episode-title">
        {{ loading ? 'Ищем следующий эпизод…' : result?.status === 'end' ? 'Сериал просмотрен' : 'Следующая серия' }}
      </h2>
      <template v-if="result?.episode">
        <strong>Сезон {{ result.episode.season_number }} · Серия {{ result.episode.number }}</strong>
        <p>{{ result.episode.name }}</p>
      </template>
      <p v-if="result?.message" class="next-episode-message">{{ result.message }}</p>
      <label
        v-if="result?.playback && ['ready', 'buffering'].includes(result.status)"
        class="next-episode-autoplay"
      >
        <input
          type="checkbox"
          :checked="autoPlay"
          @change="emit('update:autoPlay', ($event.target as HTMLInputElement).checked)"
        >
        Автоматически запускать следующую серию
      </label>
      <div class="next-episode-actions">
        <button
          v-if="result?.playback && ['ready', 'buffering'].includes(result.status)"
          class="button primary focus-ring"
          type="button"
          @click="emit('play')"
        >
          ▶ Следующая серия<span v-if="autoPlay"> · {{ countdown }}</span>
        </button>
        <button
          v-else-if="result?.episode && !result.combined_file && ['source_required', 'unavailable'].includes(result.status)"
          class="button primary focus-ring"
          type="button"
          @click="emit('choose-source')"
        >
          Выбрать источник
        </button>
        <button class="button secondary focus-ring" type="button" @click="emit('close')">
          Закрыть
        </button>
      </div>
    </section>
  </div>
</template>
