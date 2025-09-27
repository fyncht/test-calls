import asyncio
import os
from celery import Celery
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings
from app.models import Recording, Call, CallStatus
from app.utils.audio import analyze_audio

celery_app = Celery("call_service", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND)

# Отдельный движок для воркера Celery
_engine = create_async_engine(settings.DATABASE_URL, future=True, echo=False)
_Session = async_sessionmaker(_engine, expire_on_commit=False)


@celery_app.task(name="process_recording")
def process_recording_task(recording_id: int):
    asyncio.run(_process_recording(recording_id))


async def _process_recording(recording_id: int):
    async with _Session() as session:
        # 1) достаем запись
        rec = await session.get(Recording, recording_id)
        if not rec:
            return

        file_path = os.path.join(settings.MEDIA_ROOT, rec.filename)

        # 2) анализ аудио
        duration, transcript, silence_json = analyze_audio(file_path)

        # 3) сохраняем результаты
        rec.duration = duration
        rec.transcription = transcript
        rec.silence_json = silence_json

        # 4) обновляем статус звонка → ready
        call = await session.get(Call, rec.call_id)
        if call:
            call.status = CallStatus.ready

        await session.commit()
