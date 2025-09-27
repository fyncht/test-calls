from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class CallCreate(BaseModel):
    caller: str = Field(..., pattern=r"^\+\d{7,15}$")
    receiver: str = Field(..., pattern=r"^\+\d{7,15}$")
    started_at: datetime


class RecordingOut(BaseModel):
    filename: str
    duration: int | None = None
    transcription: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CallOut(BaseModel):
    id: int
    caller: str
    receiver: str
    started_at: datetime
    status: str
    recording: RecordingOut | None = None

    model_config = ConfigDict(from_attributes=True)
