FROM python:3.11-slim

# FFmpeg для pydub
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходники
COPY app /app/app

# Папка для файлов
RUN mkdir -p /data/media
VOLUME ["/data/media"]

# Порт для API
EXPOSE 8000

# По умолчанию — просто образ; команды задаются в docker-compose
