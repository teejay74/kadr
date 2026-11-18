/** Route legacy persisted TMDB images through KADR as well as new API links. */
export function imageUrl(value: string | null | undefined): string | null {
  if (!value) return null
  if (!/^https?:\/\/image\.tmdb\.org(?:\/|:)/i.test(value)) return value
  try {
    const url = new URL(value)
    const match = /^\/t\/p\/(w92|w154|w185|w300|w342|w500|w780|w1280|original)\/([A-Za-z0-9_-]{1,128}\.(?:jpg|jpeg|png|webp))$/.exec(url.pathname)
    return match && !url.search && !url.hash && !url.port && !url.username
      ? `/api/v1/posters/${match[1]}/${match[2]}` : null
  } catch {
    return null
  }
}
