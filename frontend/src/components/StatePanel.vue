<script setup lang="ts">
withDefaults(defineProps<{ title: string; message?: string; showRetry?: boolean }>(), {
  message: '',
  showRetry: false,
})
defineEmits<{ retry: [] }>()
</script>

<template>
  <div class="state-panel" role="status">
    <span class="state-mark" aria-hidden="true">◇</span>
    <h2>{{ title }}</h2>
    <p v-if="message">{{ message }}</p>
    <button v-if="showRetry" class="button secondary focus-ring" type="button" @click="$emit('retry')">
      Повторить
    </button>
  </div>
</template>
