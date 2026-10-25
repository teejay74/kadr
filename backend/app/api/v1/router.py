from fastapi import APIRouter

from app.api.v1.catalog import router as catalog_router
from app.api.v1.playback import router as playback_router
from app.api.v1.sources import router as sources_router
from app.api.v1.streaming import router as streaming_router
from app.api.v1.system import router as system_router
from app.api.v1.torrents import router as torrents_router

api_router = APIRouter()
api_router.include_router(catalog_router, tags=["catalog"])
api_router.include_router(sources_router, tags=["sources"])
api_router.include_router(torrents_router, tags=["torrents"])
api_router.include_router(streaming_router, tags=["streaming"])
api_router.include_router(playback_router, tags=["playback"])
api_router.include_router(system_router, prefix="/system", tags=["system"])
