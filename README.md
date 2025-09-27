# Call & Recording Service (FastAPI + Celery)

Сервис для хранения карточек звонков, загрузки аудиозаписей и фоновой обработки (длительность, “псевдотранскрипция”).
Стек: **FastAPI**, **PostgreSQL** (async SQLAlchemy), **Redis + Celery**, **pydub/ffmpeg**.

## Быстрый старт

### 1) Подготовка
- Установите Docker и Docker Compose v2+
- В корне уже есть `.env` (или скопируйте из `.env.example`)

### 2) Запуск
```bash
docker compose up -d --build
```

Проверка логов:
```bash
docker logs -f callsvc_api
# Должно быть: "Uvicorn running on http://0.0.0.0:8000"
```

### 3) Проверка “живости”
```bash
curl http://127.0.0.1:8000/ping     # -> "pong"
curl http://127.0.0.1:8000/health   # -> {"status":"ok"}
```

### 4) Swagger (UI)
- Откройте: `http://localhost:8000/docs`
- Альтернатива: `http://localhost:8000/redoc`

---

## Архитектура

- `api` — FastAPI-приложение
- `worker` — Celery worker (фоновая обработка аудио)
- `postgres` — БД (async SQLAlchemy)
- `redis` — брокер задач/результатов для Celery
- Файлы аудио сохраняются в volume `media` и доступны по `GET /media/<filename>`

---

## Переменные окружения (из `.env`)

```env
# БД
POSTGRES_DB=app
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/app

# Celery/Redis
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Файлы
MEDIA_ROOT=/data/media

# Presigned URL
SECRET_KEY=dev-insecure-secret
PRESIGN_TTL_SECONDS=600
```

---

## Эндпоинты

### Health / Ping
- `GET /health` → `{"status":"ok"}`
- `GET /ping` → `"pong"`

### Звонки
- `POST /calls/`
  Создать карточку звонка.
  Тело (JSON):
  ```json
  {
    "caller": "+79001234567",
    "receiver": "+74951234567",
    "started_at": "2025-09-20T10:00:00"
  }
  ```
  Ответ: `int` (ID звонка)

- `GET /calls/{id}/`
  Получить карточку звонка. Пример ответа:
  ```json
  {
    "id": 2,
    "caller": "+79001234567",
    "receiver": "+74951234567",
    "started_at": "2025-09-20T10:00:00",
    "status": "ready",
    "recording": {
      "filename": "1f42bf6d5a184235a35973ce3a0dbf4a.wav",
      "duration": 3,
      "transcription": "Detected speech fragment: -9.2 dBFS, RMS=11313"
    }
  }
  ```

- `GET /calls?q=<phone_substr>`
  Поиск по номеру (по `caller`/`receiver`, нечувствительно к регистру, `ILIKE`).

### Запись (аудио)
- `POST /calls/{id}/recording/`
  Загрузка аудио (multipart/form-data), поле `file` (поддержка: `.mp3/.wav/.ogg/.m4a`).
  Ответ:
  ```json
  {"message":"uploaded","filename":"<uuid>.<ext>"}
  ```
  После загрузки:
  - статус звонка → `processing`
  - Celery-задача считает длительность и “псевдотранскрипцию”
  - статус звонка → `ready`

### Скачивание (presigned)
- `GET /calls/{id}/presign` → выдаёт одноразовую ссылку с токеном и TTL:
  ```json
  {"url":"/calls/2/download?token=...","ttl_seconds":600}
  ```
- `GET /calls/{id}/download?token=...` → скачивание файла (если токен валиден и не истёк)

---

## Быстрый тест (manually)

> Если на машине нет `ffmpeg`, можно сгенерировать WAV одной командой Python:

```bash
python3 - <<'PY'
import wave, struct, math
fr=44100; dur=3; amp=16000; freq=1000
with wave.open('test.wav','w') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(fr)
    for i in range(fr*dur):
        val=int(amp*math.sin(2*math.pi*freq*i/fr))
        w.writeframes(struct.pack('<h', val))
print("OK: test.wav")
PY
```

1) Создаём звонок:
```bash
curl -X POST http://127.0.0.1:8000/calls/   -H "Content-Type: application/json"   -d '{"caller":"+79001234567","receiver":"+74951234567","started_at":"2025-09-20T10:00:00"}'
# → вернётся ID, например 2
```

2) Грузим запись:
```bash
curl -X POST "http://127.0.0.1:8000/calls/2/recording/"   -F "file=@test.wav"
```

3) Смотрим карточку:
```bash
curl http://127.0.0.1:8000/calls/2/
# Сначала "processing", затем "ready" (через 1–2 секунды)
```

4) Проверяем presigned download:
```bash
curl http://127.0.0.1:8000/calls/2/presign
# Возьмите "url" из ответа:
curl -L "http://127.0.0.1:8000/calls/2/download?token=...." -o out.wav
ls -lh out.wav
```

5) Поиск по номеру:
```bash
curl "http://127.0.0.1:8000/calls?q=+7900"
```

---

## Логи и отладка

Логи API:
```bash
docker logs -f callsvc_api
```

Логи воркера (фоновые задачи обработки):
```bash
docker logs -f callsvc_worker
```

Проверка эндпоинтов из контейнера (если на хосте что-то мешает):
```bash
docker exec -it callsvc_api sh -lc 'python - <<PY
import urllib.request
print(urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5).read().decode())
PY'
```

---

## Частые вопросы / Troubleshooting

**Пустой ответ (`Empty reply from server`)**
Uvicorn должен слушать `0.0.0.0`. В нашем `docker-compose.yml` команда уже в **exec-форме**:
```
python -m uvicorn app.main:app --host=0.0.0.0 --port=8000 ...
```
Проверь:
```bash
docker inspect callsvc_api --format='CMD={{.Path}} {{json .Args}}'
```

**500 / `MissingGreenlet` при доступе к связанным моделям**
Это классика async SQLAlchemy при ленивой подгрузке. В сервисе уже применена **eager-загрузка** (`selectinload`) и прямые `select(...)` там, где это важно (например, в `/presign`).

**`Unsupported file type`**
Проверьте расширение (`.mp3/.wav/.ogg/.m4a`). MIME можно видеть в DevTools/cli, но валидатор ориентируется на имя файла.

**Не вижу, что Celery что-то делает**
Смотрите `docker logs -f callsvc_worker`. При загрузке записи должна появиться таска `process_recording`.

**Сброс БД/файлов** (полностью “с чистого листа”)
```bash
docker compose down
docker volume rm test-calls_pgdata test-calls_media
docker compose up -d --build
```

---

## Статусы

- `created` — создана карточка, без записи
- `processing` — запись загружена, идёт фоновая обработка
- `ready` — обработка завершена, заполнены `duration` и “псевдотранскрипция”

---

## Технические детали

- SQLAlchemy 2.x (async engine + `async_sessionmaker`)
- Pydantic v2 (`ConfigDict(from_attributes=True)`)
- Celery 5 + Redis (broker/result)
- pydub + ffmpeg для анализа аудио
- Presigned URL на основе `itsdangerous` (TTL задаётся `PRESIGN_TTL_SECONDS`)

---
