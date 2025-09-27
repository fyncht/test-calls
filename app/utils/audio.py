import json
import os
from typing import Tuple
from pydub import AudioSegment, silence


def analyze_audio(file_path: str) -> Tuple[int, str, str]:
    """
    Возвращает: (duration_seconds, pseudo_transcript, silence_json)
    - duration: длительность в секундах
    - pseudo_transcript: текст-заглушка
    - silence_json: список интервалов тишины (мс) как JSON
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)

    seg = AudioSegment.from_file(file_path)
    duration_sec = int(round(len(seg) / 1000.0))

    # Псевдотранскрипция: берём первые 20 секунд (или меньше)
    head_ms = min(20_000, len(seg))
    head = seg[:head_ms]
    # Сгенерируем простой “фрагмент речи”: средняя громкость / RMS
    pseudo = f"Detected speech fragment: {head.dBFS:.1f} dBFS, RMS={head.rms}"

    # “Фейковый детектор тишины”
    sil = silence.detect_silence(seg, min_silence_len=700, silence_thresh=seg.dBFS - 16, seek_step=10)
    # detect_silence -> список [start_ms, end_ms]
    silence_json = json.dumps({"silence_ms": sil})

    return duration_sec, pseudo, silence_json
