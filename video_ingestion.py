"""
video_ingestion.py
Ingesta de links de YouTube para un wizard de comedia:
- Valida duración (ideal <=30 min, tolerancia hasta 45 min)
- Descarga transcripciones para construir el contexto RAG
- Extrae señales semánticas locales para reducir uso de tokens
"""
from __future__ import annotations

import logging
import re
import requests
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Dict, List, Tuple

from yt_dlp import YoutubeDL
from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)

MAX_IDEAL_MINUTES = 30
MAX_ALLOWED_MINUTES = 45

# Stopwords mínimas para extraer términos semánticos locales sin LLM.
_STOPWORDS = {
    "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las", "por", "un", "para",
    "con", "no", "una", "su", "al", "lo", "como", "más", "pero", "sus", "le", "ya", "o", "fue",
    "ha", "sí", "porque", "esta", "son", "entre", "cuando", "muy", "sin", "sobre", "también",
    "me", "mi", "tu", "te", "es", "soy", "era", "está", "estoy", "si", "yo", "él", "ella",
}


@dataclass
class VideoRecord:
    url: str
    video_id: str
    title: str
    duration_seconds: int
    transcript: str


@dataclass
class RejectedVideo:
    url: str
    reason: str
    duration_seconds: int | None = None


def extract_youtube_id(url: str) -> str | None:
    """Extrae el ID de video de URLs comunes de YouTube."""
    pattern = (
        r"(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})"
    )
    match = re.search(pattern, url)
    return match.group(1) if match else None


def _get_video_metadata(url: str) -> Dict:
    """Recupera metadatos de YouTube sin descargar video."""
    with YoutubeDL(
        {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": 12,
            "extractor_retries": 1,
        }
    ) as ydl:
        return ydl.extract_info(url, download=False)


def _duration_reason(duration_seconds: int) -> str | None:
    if duration_seconds <= MAX_IDEAL_MINUTES * 60:
        return None
    if duration_seconds <= MAX_ALLOWED_MINUTES * 60:
        return (
            "Duración dentro del margen de tolerancia (30-45 min). "
            "Se acepta, pero podría incrementar uso de tokens."
        )
    return (
        f"Video demasiado largo ({duration_seconds // 60} min). "
        "Para controlar consumo de tokens en Google AI Studio, usa videos de hasta 45 min."
    )


def _normalize_transcript_items(transcript_items) -> str:
    """Convierte distintas estructuras de transcript en texto plano."""
    chunks: List[str] = []
    for item in transcript_items:
        if isinstance(item, dict):
            text = item.get("text", "")
        else:
            text = getattr(item, "text", "")
        if text:
            chunks.append(text)
    return " ".join(chunks).strip()


def _fetch_transcript(video_id: str) -> str:
    """Descarga transcript soportando APIs antiguas y nuevas del paquete."""
    errors: List[str] = []

    # API nueva (v1.x): instancia + fetch(...)
    try:
        api = YouTubeTranscriptApi()
        if hasattr(api, "fetch"):
            for langs in (["es", "en"], ["es"], ["en"]):
                try:
                    transcript_items = api.fetch(video_id, languages=langs)
                    joined = _normalize_transcript_items(transcript_items)
                    if joined:
                        return joined
                except Exception as exc:
                    errors.append(f"fetch({langs}): {exc}")
    except Exception as exc:
        errors.append(f"api() init: {exc}")

    # API nueva alternativa: instancia + list(...)
    try:
        api = YouTubeTranscriptApi()
        if hasattr(api, "list"):
            transcript_list = api.list(video_id)
            for transcript in transcript_list:
                lang = getattr(transcript, "language_code", "")
                if lang in {"es", "en"}:
                    transcript_items = transcript.fetch()
                    joined = _normalize_transcript_items(transcript_items)
                    if joined:
                        return joined
            for transcript in transcript_list:
                transcript_items = transcript.fetch()
                joined = _normalize_transcript_items(transcript_items)
                if joined:
                    return joined
    except Exception as exc:
        errors.append(f"list(): {exc}")

    # API antigua (v0.x): métodos estáticos
    for langs in (["es", "en"], ["es"], ["en"], None):
        try:
            if langs is None:
                transcript_items = YouTubeTranscriptApi.get_transcript(video_id)
            else:
                transcript_items = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
            joined = _normalize_transcript_items(transcript_items)
            if joined:
                return joined
        except Exception as exc:
            errors.append(f"get_transcript({langs}): {exc}")

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        for langs in (["es"], ["en"]):
            try:
                transcript_items = transcript_list.find_transcript(langs).fetch()
                joined = _normalize_transcript_items(transcript_items)
                if joined:
                    return joined
            except Exception as exc:
                errors.append(f"find_transcript({langs}): {exc}")
    except Exception as exc:
        errors.append(f"list_transcripts(): {exc}")

    # Diagnóstico básico: validar si YouTube expone captions en HTML.
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        has_captions = response.status_code == 200 and '"captions"' in response.text
        errors.append(f"html_captions={has_captions}")
    except Exception as exc:
        errors.append(f"html_check: {exc}")

    raise ValueError(
        "No se pudo obtener transcripción para "
        f"{video_id}. Detalle: {' | '.join(errors[:3])}"
    )



def _run_with_timeout(func, args: tuple, timeout_seconds: int):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args)
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeoutError:
            raise TimeoutError(f"Tiempo de espera excedido ({timeout_seconds}s)")


def validate_and_collect_videos(urls: List[str]) -> Tuple[List[VideoRecord], List[RejectedVideo], List[str]]:
    """
    Valida links, duración y transcript.

    Returns:
      accepted: videos listos para RAG
      rejected: videos rechazados con razón
      warnings: advertencias (ej: 30-45 min)
    """
    accepted: List[VideoRecord] = []
    rejected: List[RejectedVideo] = []
    warnings: List[str] = []

    for raw_url in urls:
        url = raw_url.strip()
        if not url:
            continue

        video_id = extract_youtube_id(url)
        if not video_id:
            rejected.append(RejectedVideo(url=url, reason="URL no parece ser un video válido de YouTube."))
            continue

        # 1. Intentar obtener transcript primero
        try:
            transcript = _run_with_timeout(_fetch_transcript, (video_id,), timeout_seconds=25)
            if not transcript:
                raise ValueError("Transcript vacío")
        except Exception as exc:
            rejected.append(
                RejectedVideo(
                    url=url,
                    reason=f"No se pudo descargar transcript: {exc}",
                    duration_seconds=None,
                )
            )
            continue

        # 2. Intentar obtener metadata, pero no rechazar si falla
        duration_seconds = -1
        title = f"Video {video_id}"
        try:
            metadata = _run_with_timeout(_get_video_metadata, (url,), timeout_seconds=20)
            duration_seconds = int(metadata.get("duration") or -1)
            title = metadata.get("title") or title
        except Exception as exc:
            warnings.append(f"No se pudo leer metadata del video: {exc}. Se usará título y duración por defecto.")

        reason = _duration_reason(duration_seconds) if duration_seconds > 0 else None
        if reason and duration_seconds > MAX_ALLOWED_MINUTES * 60:
            rejected.append(
                RejectedVideo(url=url, reason=reason, duration_seconds=duration_seconds)
            )
            continue
        if reason:
            warnings.append(f"{title}: {reason}")

        accepted.append(
            VideoRecord(
                url=url,
                video_id=video_id,
                title=title,
                duration_seconds=duration_seconds,
                transcript=transcript,
            )
        )

    return accepted, rejected, warnings


def extract_semantic_signals(texts: List[str], top_k: int = 20) -> List[str]:
    """
    Extracción semántica local básica para reducir tokens enviados a Gemini.
    Produce una lista de términos frecuentes no triviales.
    """
    freq: Dict[str, int] = {}
    for text in texts:
        tokens = re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ]{4,}", text.lower())
        for token in tokens:
            if token in _STOPWORDS:
                continue
            freq[token] = freq.get(token, 0) + 1

    ranked = sorted(freq.items(), key=lambda item: item[1], reverse=True)
    return [term for term, _ in ranked[:top_k]]
