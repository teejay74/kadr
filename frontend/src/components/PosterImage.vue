<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { imageUrl } from '../services/images'

const props = withDefaults(defineProps<{
  src?: string | null
  alt?: string
  placeholder?: string
  placeholderClass?: string
  loading?: 'lazy' | 'eager'
}>(), { src: null, alt: '', loading: 'lazy', placeholder: 'K', placeholderClass: 'poster-placeholder' })
const failed = ref(false)
const source = computed(() => imageUrl(props.src))
watch(source, () => { failed.value = false })
</script>

<template>
  <img v-if="source && !failed" :src="source" :alt="alt" :loading="loading" @error="failed = true" />
  <div v-else :class="placeholderClass" aria-hidden="true">{{ placeholder }}</div>
</template>
