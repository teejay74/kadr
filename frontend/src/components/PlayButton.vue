<script setup lang="ts">
withDefaults(defineProps<{
  label?: string
  disabled?: boolean
}>(), {
  label: 'Смотреть',
  disabled: false,
})

defineEmits<{ play: [] }>()
</script>

<template>
  <button
    class="button primary focus-ring play-button"
    type="button"
    :disabled="disabled"
    @click="$emit('play')"
  >
    <span aria-hidden="true">▶</span>
    {{ label }}
  </button>
</template>
