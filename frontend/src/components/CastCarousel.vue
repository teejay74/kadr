<script setup lang="ts">
import PosterImage from './PosterImage.vue'
import type { CastMember } from '../types/media'

defineProps<{ cast: CastMember[] }>()
</script>

<template>
  <section v-if="cast.length" class="details-section" aria-labelledby="cast-title">
    <h2 id="cast-title">В ролях</h2>
    <div class="cast-grid">
      <article v-for="person in cast" :key="person.id" class="cast-card">
        <PosterImage :src="person.profile_url" :placeholder="person.name.slice(0, 1)" placeholder-class="avatar-placeholder" :alt="person.name" loading="lazy" />
        <strong>{{ person.name }}</strong>
        <span>{{ person.character }}</span>
      </article>
    </div>
  </section>
</template>
