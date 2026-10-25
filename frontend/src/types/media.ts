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

export type SourceSort = 'seeders' | 'size' | 'resolution' | 'source' | 'title'
export type SortOrder = 'asc' | 'desc'

export interface SourceRelease {
  id: string
  title: string
  indexer: string
  size_bytes: number
  seeders: number | null
  peers: number | null
  published_at: string | null
  protocol: 'torrent'
  resolution: string | null
  source: string | null
  codec: string | null
  hdr: boolean
  hdr_format: string | null
  audio: string | null
  language: string | null
  release_type: string | null
}

export interface SourceResults {
  media_id: number
  media_kind: MediaKind
  query: string
  items: SourceRelease[]
  total: number
}

export interface TorrentFile {
  id: number
  name: string
  size_bytes: number
  progress: number
  priority: number
  is_video: boolean
}

export interface TorrentStatus {
  id: string
  media_id: number
  media_kind: MediaKind
  name: string
  state: string
  progress: number
  downloaded_bytes: number
  total_size_bytes: number
  download_speed_bytes: number
  upload_speed_bytes: number
  peers: number
  seeds: number
  eta_seconds: number | null
  selected_file_id: number | null
  selected_file_path: string | null
  can_start: boolean
  can_stop: boolean
}

export interface StreamReadiness {
  ready: boolean
  buffer_progress: number
}

export type PlaybackPreparationState = 'idle' | 'probing' | 'processing' | 'ready' | 'failed'
export type PlaybackStrategy = 'remux' | 'audio_transcode' | 'transcode'

export interface PlaybackPreparation {
  state: PlaybackPreparationState
  progress: number
  strategy: PlaybackStrategy | null
  video_codec: string | null
  audio_codec: string | null
  message: string | null
  stream_url: string | null
}
