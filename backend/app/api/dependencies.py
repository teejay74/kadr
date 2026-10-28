from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.repositories.episodes import EpisodeRepository
from app.repositories.library import LibraryRepository
from app.repositories.metadata_cache import MetadataCacheRepository
from app.repositories.torrent_tasks import TorrentTaskRepository
from app.services.cache.manager import CacheManager
from app.services.episodes.matcher import EpisodeMatcher
from app.services.library.manager import LibraryManager
from app.services.metadata.catalog import CatalogService
from app.services.metadata.tmdb import TMDBClient
from app.services.playback.manager import CompatibilityManager
from app.services.playback.navigation import EpisodeNavigationService
from app.services.playback.resolver import PlaybackResolver
from app.services.playback.service import PlaybackPreparationService
from app.services.playback.tracks import PlaybackTrackProbe, PlaybackTrackService
from app.services.sources.prowlarr import ProwlarrClient
from app.services.sources.search import SourceSearchService
from app.services.streaming.manager import StreamingManager
from app.services.streaming.registry import StreamRegistry
from app.services.torrents.manager import TorrentManager
from app.services.torrents.qbittorrent import QBittorrentClient


def get_catalog_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CatalogService:
    settings = get_settings()
    return CatalogService(
        TMDBClient(request.app.state.metadata_http_client, settings),
        MetadataCacheRepository(session),
        settings,
    )


CatalogServiceDependency = Annotated[CatalogService, Depends(get_catalog_service)]


def get_source_search_service(
    request: Request,
    catalog: CatalogServiceDependency,
) -> SourceSearchService:
    settings = get_settings()
    return SourceSearchService(
        catalog,
        ProwlarrClient(request.app.state.indexer_http_client, settings),
    )


SourceSearchServiceDependency = Annotated[
    SourceSearchService,
    Depends(get_source_search_service),
]


def get_torrent_manager(
    request: Request,
    sources: SourceSearchServiceDependency,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TorrentManager:
    settings = get_settings()
    return TorrentManager(
        QBittorrentClient(request.app.state.torrent_http_client, settings),
        sources,
        TorrentTaskRepository(session),
        settings,
        EpisodeRepository(session),
    )


TorrentManagerDependency = Annotated[TorrentManager, Depends(get_torrent_manager)]


def get_episode_matcher(
    catalog: CatalogServiceDependency,
    torrents: TorrentManagerDependency,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EpisodeMatcher:
    return EpisodeMatcher(
        catalog,
        torrents,
        TorrentTaskRepository(session),
        EpisodeRepository(session),
    )


EpisodeMatcherDependency = Annotated[EpisodeMatcher, Depends(get_episode_matcher)]


def get_streaming_manager(
    request: Request,
    torrents: TorrentManagerDependency,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingManager:
    settings = get_settings()
    registry: StreamRegistry = request.app.state.stream_registry
    return StreamingManager(
        QBittorrentClient(request.app.state.torrent_http_client, settings),
        torrents,
        TorrentTaskRepository(session),
        registry,
        settings,
    )


StreamingManagerDependency = Annotated[StreamingManager, Depends(get_streaming_manager)]


def get_compatibility_manager(request: Request) -> CompatibilityManager:
    return request.app.state.compatibility_manager  # type: ignore[no-any-return]


CompatibilityManagerDependency = Annotated[
    CompatibilityManager,
    Depends(get_compatibility_manager),
]


def get_playback_preparation_service(
    request: Request,
    manager: CompatibilityManagerDependency,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PlaybackPreparationService:
    settings = get_settings()
    return PlaybackPreparationService(
        manager,
        QBittorrentClient(request.app.state.torrent_http_client, settings),
        TorrentTaskRepository(session),
        settings,
    )


PlaybackPreparationServiceDependency = Annotated[
    PlaybackPreparationService,
    Depends(get_playback_preparation_service),
]


def get_playback_track_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PlaybackTrackService:
    settings = get_settings()
    probe: PlaybackTrackProbe = request.app.state.playback_track_probe
    return PlaybackTrackService(
        probe,
        TorrentTaskRepository(session),
        LibraryRepository(session),
        QBittorrentClient(request.app.state.torrent_http_client, settings),
        settings,
    )


PlaybackTrackServiceDependency = Annotated[
    PlaybackTrackService,
    Depends(get_playback_track_service),
]


def get_library_manager(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LibraryManager:
    settings = get_settings()
    return LibraryManager(
        LibraryRepository(session),
        TorrentTaskRepository(session),
        QBittorrentClient(request.app.state.torrent_http_client, settings),
        request.app.state.stream_registry,
        settings,
        EpisodeRepository(session),
    )


LibraryManagerDependency = Annotated[LibraryManager, Depends(get_library_manager)]


def get_playback_resolver(
    torrents: TorrentManagerDependency,
    streaming: StreamingManagerDependency,
    library_manager: LibraryManagerDependency,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PlaybackResolver:
    return PlaybackResolver(
        EpisodeRepository(session),
        LibraryRepository(session),
        TorrentTaskRepository(session),
        library_manager,
        torrents,
        streaming,
    )


PlaybackResolverDependency = Annotated[
    PlaybackResolver,
    Depends(get_playback_resolver),
]


def get_episode_navigation_service(
    catalog: CatalogServiceDependency,
    resolver: PlaybackResolverDependency,
    torrents: TorrentManagerDependency,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EpisodeNavigationService:
    return EpisodeNavigationService(
        catalog,
        resolver,
        EpisodeRepository(session),
        torrents,
    )


EpisodeNavigationServiceDependency = Annotated[
    EpisodeNavigationService,
    Depends(get_episode_navigation_service),
]


def get_cache_manager(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CacheManager:
    settings = get_settings()
    return CacheManager(
        TorrentTaskRepository(session),
        LibraryRepository(session),
        QBittorrentClient(request.app.state.torrent_http_client, settings),
        request.app.state.stream_registry,
        request.app.state.compatibility_manager,
        settings,
    )


CacheManagerDependency = Annotated[CacheManager, Depends(get_cache_manager)]
