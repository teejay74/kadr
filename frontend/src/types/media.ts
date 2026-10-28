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

export interface EpisodeSummary {
  id: number
  season_number: number
  number: number
  name: string
  overview: string
  air_date: string | null
  runtime_minutes: number | null
  still_url: string | null
  rating: number
}

export interface SeasonDetails {
  id: number
  series_id: number
  number: number
  name: string
  overview: string
  air_date: string | null
  poster_url: string | null
  episodes: EpisodeSummary[]
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
  season_number: number | null
  season_numbers: number[]
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
  duration_seconds: number | null
}

export interface EpisodeFileBinding {
  id: string
  episode_id: string
  media_id: number
  season_number: number
  episode_number: number
  catalog_episode_id: number | null
  file_variant_id: string
  file_id: number
  variant_label: string | null
  confidence: EpisodeMatchConfidence
  confirmation: 'automatic' | 'manual'
  segment_index: number | null
}

export type EpisodeMatchConfidence = 'exact' | 'probable' | 'ambiguous'

export interface EpisodeMatchIdentity {
  season_number: number
  episode_number: number
  catalog_episode_id: number | null
  name: string
  runtime_minutes: number | null
}

export interface EpisodeMatchFile {
  file_id: number
  file_path: string
  confidence: EpisodeMatchConfidence
  episodes: EpisodeMatchIdentity[]
  alternatives: EpisodeMatchIdentity[]
  reasons: string[]
  confirmed: boolean
  confirmation: 'automatic' | 'manual' | null
  unsafe: boolean
  duration_seconds: number | null
}

export interface EpisodeMatchReport {
  task_id: string
  metadata_available: boolean
  files: EpisodeMatchFile[]
  requires_confirmation: boolean
}

export interface EpisodeMatchSelection {
  file_id: number
  episodes: EpisodeMatchIdentity[]
  segment_index?: number | null
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

export interface CacheFileDeletion {
  task_id: string
  file_id: number
  reclaimed_bytes: number
  selected_file_cleared: boolean
}

export interface StreamReadiness {
  ready: boolean
  buffer_progress: number
  file_progress: number
  download_state: string | null
  download_speed_bytes: number
}

export type PlaybackPreparationState = 'idle' | 'probing' | 'processing' | 'ready' | 'failed'
export type PlaybackMode = 'compatible' | 'audio_only' | 'audio_track'
export type PlaybackStrategy = 'remux' | 'audio_transcode' | 'transcode'

export interface PlaybackPreparation {
  mode: PlaybackMode
  state: PlaybackPreparationState
  progress: number
  strategy: PlaybackStrategy | null
  video_codec: string | null
  audio_codec: string | null
  message: string | null
  stream_url: string | null
  track_id: string | null
}

export type PlaybackTrackKind = 'audio' | 'subtitle'
export type PlaybackTrackDelivery =
  | 'native_or_compatible'
  | 'external_webvtt'
  | 'burn_in_required'
  | 'unsupported'

export interface PlaybackTrack {
  id: string
  preference_key: string
  stream_index: number
  kind: PlaybackTrackKind
  language: string | null
  codec: string
  title: string | null
  is_default: boolean
  is_forced: boolean
  is_hearing_impaired: boolean
  channels: number | null
  channel_layout: string | null
  delivery: PlaybackTrackDelivery
}

export interface PlaybackTrackList {
  source: 'library' | 'torrent'
  source_id: string
  file_id: number | null
  audio_tracks: PlaybackTrack[]
  subtitle_tracks: PlaybackTrack[]
  selected_audio_track_id: string | null
  selected_subtitle_track_id: string | null
  subtitles_enabled: boolean
}

export interface PlaybackTrackPreferencePayload {
  profile_key: string
  audio_track_id: string | null
  subtitle_track_id: string | null
  subtitles_enabled: boolean
}

export interface PlaybackSubtitlePreparation {
  track_id: string
  stream_url: string
}

export type PlaybackResolutionStatus =
  | 'ready'
  | 'buffering'
  | 'source_required'
  | 'unavailable'

export interface PlaybackResolution {
  status: PlaybackResolutionStatus
  source: 'library' | 'torrent' | null
  stream_url: string | null
  task_id: string | null
  file_id: number | null
  library_item_id: string | null
  resume_position_seconds: number
  buffer_progress: number
  download_progress: number
  download_state: string | null
  download_speed_bytes: number
  message: string | null
}

export type NextEpisodeStatus = PlaybackResolutionStatus | 'end'

export interface NextEpisodeResolution {
  status: NextEpisodeStatus
  episode: EpisodeSummary | null
  playback: PlaybackResolution | null
  prefetched: boolean
  combined_file: boolean
  message: string | null
}

export interface MediaSnapshot {
  media_id: number
  media_kind: MediaKind
  title: string
  original_title: string
  poster_url: string | null
  backdrop_url: string | null
}

export interface LibraryItem extends MediaSnapshot {
  id: string
  task_id: string
  file_id: number | null
  episode: PersistedEpisodeIdentity | null
  size_bytes: number
  created_at: string
  stream_url: string
}

export interface PersistedEpisodeIdentity {
  id: string
  media_id: number
  season_number: number
  episode_number: number
  catalog_episode_id: number | null
}

export interface FavoriteItem extends MediaSnapshot {
  id: string
  created_at: string
}

export interface HistoryItem {
  id: string
  media_id: number
  media_kind: MediaKind
  profile_key: string
  season_number: number | null
  episode_number: number | null
  catalog_episode_id: number | null
  episode: PersistedEpisodeIdentity | null
  title: string
  poster_url: string | null
  position_seconds: number
  duration_seconds: number
  completed: boolean
  updated_at: string
}
