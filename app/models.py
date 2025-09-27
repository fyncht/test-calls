from __future__ import annotations

import enum
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, Enum, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CallStatus(str, enum.Enum):
    created = "created"
    processing = "processing"
    ready = "ready"


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    caller: Mapped[str] = mapped_column(String(20), index=True)
    receiver: Mapped[str] = mapped_column(String(20), index=True)
    started_at: Mapped[datetime]

    status: Mapped[CallStatus] = mapped_column(Enum(CallStatus), default=CallStatus.created, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                                                 nullable=False)

    recording: Mapped["Recording"] = relationship(back_populates="call", uselist=False)


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"), unique=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    duration: Mapped[int | None] = mapped_column(Integer)  # seconds
    transcription: Mapped[str | None] = mapped_column(Text)

    silence_json: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                                                 nullable=False)

    call: Mapped[Call] = relationship(back_populates="recording")
