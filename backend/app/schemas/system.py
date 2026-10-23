from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: Literal["kadr-api"] = "kadr-api"
    version: str = "0.1.0"
    database: Literal["ok", "unavailable"]


class ErrorResponse(BaseModel):
    code: str
    message: str

