from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.services.posters.manager import poster_path

router = APIRouter()


@router.get(
    "/posters/{size}/{filename}",
    response_class=Response,
    responses={
        200: {
            "content": {
                mime: {}
                for mime in (
                    "image/jpeg",
                    "image/png",
                    "image/webp",
                )
            }
        }
    },
)
async def get_poster(size: str, filename: str, request: Request) -> Response:
    if poster_path(size, filename) is None or request.query_params:
        return JSONResponse(
            status_code=422,
            content={
                "code": "invalid_poster",
                "message": "Invalid poster size or filename",
            },
        )
    data, mime = await request.app.state.poster_manager.get(size, filename)
    ttl = request.app.state.poster_manager.settings.poster_cache_ttl_seconds
    return Response(
        data,
        media_type=mime,
        headers={
            "Cache-Control": f"public, max-age={ttl}",
            "X-Content-Type-Options": "nosniff",
        },
    )
