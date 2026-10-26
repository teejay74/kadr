from typing import Literal

from pydantic import BaseModel, Field

PlaybackState = Literal["idle", "probing", "processing", "ready", "failed"]
PlaybackMode = Literal["compatible", "audio_only"]
PlaybackStrategy = Literal["remux", "audio_transcode", "transcode"]


class PlaybackPreparation(BaseModel):
    mode: PlaybackMode = "compatible"
    state: PlaybackState
    progress: float = Field(ge=0, le=1)
    strategy: PlaybackStrategy | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    message: str | None = None
    stream_url: str | None = None
