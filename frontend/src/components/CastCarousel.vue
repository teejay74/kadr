<script setup lang="ts">
import type { CastMember } from '../types/media'

defineProps<{ cast: CastMember[] }>()
</script>

<template>
  <section v-if="cast.length" class="details-section" aria-labelledby="cast-title">
    <h2 id="cast-title">В ролях</h2>
    <div class="cast-grid">
      <article v-for="person in cast" :key="person.id" class="cast-card">
        <img v-if="person.profile_url" :src="person.profile_url" :alt="person.name" loading="lazy" />
        <div v-else class="avatar-placeholder" aria-hidden="true">{{ person.name.slice(0, 1) }}</div>
        <strong>{{ person.name }}</strong>
        <span>{{ person.character }}</span>
      </article>
    </div>
  </section>
</template>
