export type MediaKind = 'movie' | 'series'
export type SortMode = 'popular' | 'rating' | 'newest'

export interface Genre {
  id: number
  name: string
}

export interface CastMember {
  id: number
  name: string
  character: string | null
  profile_url: string | null
}

export interface SeasonSummary {
  id: number
  number: number
  name: string
  episode_count: number
  air_date: string | null
  poster_url: string | null
}

export interface MediaCardData {
  id: number
  kind: MediaKind
  title: string
  original_title: string
  overview: string
  release_date: string | null
  year: number | null
  poster_url: string | null
  backdrop_url: string | null
  rating: number
  popularity: number
  genre_ids: number[]
}

export interface MediaPage {
  items: MediaCardData[]
  page: number
  total_pages: number
  total_results: number
}

export interface MediaDetails extends MediaCardData {
  genres: Genre[]
  runtime_minutes: number | null
  status: string | null
  tagline: string | null
  cast: CastMember[]
  trailer_url: string | null
  seasons: SeasonSummary[]
  season_count: number | null
  episode_count: number | null
}

export interface CatalogQuery {
  page?: number
  sort?: SortMode
  genre?: number | null
  year?: number | null
}
