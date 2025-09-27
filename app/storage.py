import os
import uuid
from fastapi import UploadFile
from app.config import settings


def ensure_media_dir():
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)


def save_upload_file(file: UploadFile) -> str:
    """
    Сохраняет загруженный файл в MEDIA_ROOT, возвращает итоговое имя файла.
    """
    ensure_media_dir()
    ext = os.path.splitext(file.filename or "")[1].lower() or ".bin"
    fname = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(settings.MEDIA_ROOT, fname)
    with open(dest_path, "wb") as f:
        f.write(file.file.read())
    return fname
