import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from sqlalchemy.orm import selectinload
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from itsdangerous import TimestampSigner, BadSignature, SignatureExpired

from app.config import settings
from app.database import get_session, init_models
from app.models import Call, Recording, CallStatus
from app.schemas import CallCreate, CallOut
from app.storage import save_upload_file
from app.tasks import celery_app  # ок импортировать, проблем не будет

logger = logging.getLogger("uvicorn.error")

# Раздача медиа
os.makedirs(settings.MEDIA_ROOT, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_models()
        yield
    except Exception:
        logger.exception("Startup failed")
        raise


app = FastAPI(title="Call & Recording Service", lifespan=lifespan)
app.mount("/media", StaticFiles(directory=settings.MEDIA_ROOT), name="media")


@app.get("/ping")
def ping():
    return "pong"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/calls/", response_model=int)
async def create_call(payload: CallCreate, session: AsyncSession = Depends(get_session)):
    call = Call(
        caller=payload.caller,
        receiver=payload.receiver,
        started_at=payload.started_at,
        status=CallStatus.created,
    )
    session.add(call)
    await session.commit()
    await session.refresh(call)
    return call.id


@app.post("/calls/{call_id}/recording/", response_model=dict)
async def upload_recording(call_id: int, file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    call = await session.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    # Сохраняем файл
    if not file.filename or not any(file.filename.lower().endswith(ext) for ext in (".mp3", ".wav", ".ogg", ".m4a")):
        raise HTTPException(status_code=400, detail="Unsupported file type. Use mp3/wav/ogg/m4a")

    filename = save_upload_file(file)

    # Создаем/обновляем запись о файле
    existing = await session.scalar(select(Recording).where(Recording.call_id == call_id))
    if existing:
        existing.filename = filename
        existing.duration = None
        existing.transcription = None
    else:
        rec = Recording(call_id=call_id, filename=filename)
        session.add(rec)

    call.status = CallStatus.processing
    await session.commit()

    # Узнаем ID записи
    recording = await session.scalar(select(Recording).where(Recording.call_id == call_id))
    # Кидаем задачу в Celery
    celery_app.send_task("process_recording", args=[recording.id])

    return {"message": "uploaded", "filename": filename}


@app.get("/calls/{call_id}/", response_model=CallOut)
async def get_call(call_id: int, session: AsyncSession = Depends(get_session)):
    stmt = (
        select(Call)
            .options(selectinload(Call.recording))
            .where(Call.id == call_id)
            .limit(1)
    )
    call = await session.scalar(stmt)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call


@app.get("/calls", response_model=list[CallOut])
async def search_calls(q: Optional[str] = Query(default=None, description="Query by phone (+7...)"),
                       session: AsyncSession = Depends(get_session)):
    stmt = select(Call).options(selectinload(Call.recording))
    if q:
        stmt = stmt.where(or_(Call.caller.ilike(f"%{q}%"), Call.receiver.ilike(f"%{q}%")))
    stmt = stmt.order_by(Call.id.desc()).limit(100)
    rows = (await session.scalars(stmt)).all()
    return rows


def _signer() -> TimestampSigner:
    return TimestampSigner(settings.SECRET_KEY)


@app.get("/calls/{call_id}/presign")
async def get_presigned(call_id: int, session: AsyncSession = Depends(get_session)):
    # Не трогаем call.recording (ленивая загрузка в async ломает поток)
    rec = await session.scalar(
        select(Recording).where(Recording.call_id == call_id).limit(1)
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Recording not found")

    token = _signer().sign(str(rec.id)).decode()
    return {
        "url": f"/calls/{call_id}/download?token={token}",
        "ttl_seconds": settings.PRESIGN_TTL_SECONDS,
    }


@app.get("/calls/{call_id}/download")
async def download_presigned(call_id: int, token: str, session: AsyncSession = Depends(get_session)):
    try:
        recording_id = int(_signer().unsign(token, max_age=settings.PRESIGN_TTL_SECONDS).decode())
    except SignatureExpired:
        raise HTTPException(status_code=403, detail="Link expired")
    except BadSignature:
        raise HTTPException(status_code=403, detail="Bad signature")

    rec = await session.get(Recording, recording_id)
    if not rec or rec.call_id != call_id:
        raise HTTPException(status_code=404, detail="Recording not found")

    path = os.path.join(settings.MEDIA_ROOT, rec.filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File missing")
    return FileResponse(path, media_type="application/octet-stream", filename=rec.filename)
