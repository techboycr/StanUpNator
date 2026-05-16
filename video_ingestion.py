"""
video_ingestion.py
Ingesta de links de YouTube para un wizard de comedia:
- Valida duración (ideal <=30 min, tolerancia hasta 45 min)
- Descarga transcripciones para construir el contexto RAG
- Extrae señales semánticas locales para reducir uso de tokens
"""
from __future__ import annotations

import logging
import os
import re
import time
import requests
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Callable, Dict, List, Optional, Tuple

from yt_dlp import YoutubeDL
from youtube_transcript_api import YouTubeTranscriptApi
from transcription_api_client import (
    TranscriptionApiClient,
    TranscriptionApiError,
    extract_transcript_text,
)

logger = logging.getLogger(__name__)

MAX_IDEAL_MINUTES = 30
MAX_ALLOWED_MINUTES = 45

_TRANSCRIPTION_API_BASE_URL = os.getenv("TRANSCRIPTION_API_BASE_URL", "http://127.0.0.1:3001").strip()
_TRANSCRIPTION_API_TOKEN = os.getenv("TRANSCRIPTION_API_ACCESS_TOKEN", "test").strip()
_TRANSCRIPTION_API_PROFILE = os.getenv("TRANSCRIPTION_API_MODEL_PROFILE", "balanced-es").strip() or "balanced-es"
_TRANSCRIPTION_POLL_TIMEOUT = int(os.getenv("TRANSCRIPTION_API_POLL_TIMEOUT_SECONDS", "240"))
_TRANSCRIPTION_POLL_INTERVAL = int(os.getenv("TRANSCRIPTION_API_POLL_INTERVAL_SECONDS", "3"))
_ENABLE_LEGACY_YOUTUBE_FALLBACK = (
    os.getenv("STANDUP_ENABLE_YT_TRANSCRIPT_FALLBACK", "false").strip().lower() in {"1", "true", "yes", "on"}
)

TranscriptionProgressCallback = Callable[[Dict[str, object]], None]

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


def _build_fallback_transcript(video_id: str, metadata: Dict) -> str:
    """Construye contexto textual cuando YouTube bloquea subtítulos en cloud."""
    title = (metadata.get("title") or "").strip()
    description = (metadata.get("description") or "").strip()
    uploader = (metadata.get("uploader") or metadata.get("channel") or "").strip()
    tags = metadata.get("tags") or []
    if not isinstance(tags, list):
        tags = []

    parts: List[str] = []
    if title:
        parts.append(f"Titulo: {title}.")
    if uploader:
        parts.append(f"Canal: {uploader}.")
    if description:
        parts.append(f"Descripcion: {description[:1400]}.")
    if tags:
        tags_clean = [str(t).strip() for t in tags[:25] if str(t).strip()]
        if tags_clean:
            parts.append(f"Etiquetas: {', '.join(tags_clean)}.")

    if parts:
        return " ".join(parts)

    # Último recurso: no bloquear el flujo aunque no exista metadata útil.
    return (
        f"Video de referencia {video_id}. "
        "No fue posible acceder a subtitulos o metadata completa desde este entorno cloud. "
        "Usar como señal temática general de comedia."
    )


def _fetch_transcript_from_cluster(url: str, duration_seconds: int | None = None) -> str:
    """Obtiene transcript via API local del cluster de transcripciones."""
    return _fetch_transcript_from_cluster_with_progress(url=url, duration_seconds=duration_seconds)


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _emit_progress(
    progress_callback: Optional[TranscriptionProgressCallback],
    payload: Dict[str, object],
) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(payload)
    except Exception as exc:
        logger.warning(f"No se pudo emitir progreso de transcripcion: {exc}")


def _fetch_transcript_from_cluster_with_progress(
    *,
    url: str,
    duration_seconds: int | None = None,
    progress_callback: Optional[TranscriptionProgressCallback] = None,
    video_index: int = 1,
    total_videos: int = 1,
    title: str = "",
) -> str:
    """Obtiene transcript via API local y publica progreso por fase cuando hay callback."""
    client = TranscriptionApiClient(
        base_url=_TRANSCRIPTION_API_BASE_URL,
        access_token=_TRANSCRIPTION_API_TOKEN,
        timeout_seconds=20,
    )

    create_payload = client.create_job(
        url=url,
        mode="async",
        model_profile=_TRANSCRIPTION_API_PROFILE,
        duration_seconds=duration_seconds,
    )

    if "job_id" not in create_payload:
        detail = create_payload.get("detail", "respuesta inesperada al crear job")
        raise TranscriptionApiError(f"No se pudo crear job de transcripcion: {detail}", payload=create_payload)

    job_id = str(create_payload["job_id"])
    initial_runtime = create_payload.get("runtime") if isinstance(create_payload, dict) else {}
    initial_phase = "queued"
    initial_progress = 5
    initial_next_poll = _TRANSCRIPTION_POLL_INTERVAL
    initial_message = "Job de transcripcion en cola"

    if isinstance(initial_runtime, dict):
        initial_phase = str(initial_runtime.get("phase") or initial_phase)
        initial_progress = _safe_int(initial_runtime.get("progress_percent"), initial_progress)
        initial_next_poll = _safe_int(initial_runtime.get("next_poll_after_seconds"), initial_next_poll)
        initial_message = str(initial_runtime.get("message") or initial_message)

    _emit_progress(
        progress_callback,
        {
            "job_id": job_id,
            "url": url,
            "title": title,
            "video_index": video_index,
            "total_videos": total_videos,
            "status": str(create_payload.get("status", "queued")).lower(),
            "phase": initial_phase,
            "progress_percent": max(0, min(100, initial_progress)),
            "next_poll_after_seconds": max(1, initial_next_poll),
            "eta_seconds": initial_runtime.get("eta_seconds") if isinstance(initial_runtime, dict) else None,
            "message": initial_message,
        },
    )

    started = time.time()
    job: Dict[str, object] = {}
    while True:
        job = client.get_job(job_id)
        status = str(job.get("status", "")).lower()
        runtime = job.get("runtime") if isinstance(job, dict) else {}
        phase = status or "queued"
        progress_percent = 0
        next_poll = _TRANSCRIPTION_POLL_INTERVAL
        eta_seconds = None
        message = f"Estado: {phase}"

        if isinstance(runtime, dict):
            phase = str(runtime.get("phase") or phase)
            progress_percent = _safe_int(runtime.get("progress_percent"), progress_percent)
            next_poll = _safe_int(runtime.get("next_poll_after_seconds"), next_poll)
            eta_seconds = runtime.get("eta_seconds")
            message = str(runtime.get("message") or message)

        progress_percent = max(0, min(100, progress_percent))
        next_poll = max(1, next_poll)

        _emit_progress(
            progress_callback,
            {
                "job_id": job_id,
                "url": url,
                "title": title,
                "video_index": video_index,
                "total_videos": total_videos,
                "status": status,
                "phase": phase,
                "progress_percent": progress_percent,
                "next_poll_after_seconds": next_poll,
                "eta_seconds": eta_seconds,
                "message": message,
            },
        )

        if status in {"completed", "failed", "cancelled"}:
            break

        if time.time() - started > _TRANSCRIPTION_POLL_TIMEOUT:
            raise TranscriptionApiError(
                f"Timeout esperando estado terminal para job {job_id}",
                payload={"last_status": status, "job_id": job_id},
            )

        time.sleep(next_poll)

    status = str(job.get("status", "")).lower()
    if status != "completed":
        detail = job.get("status_detail") or job.get("detail") or "sin detalle"
        raise TranscriptionApiError(
            f"Job {job_id} finalizo en estado '{status}'",
            payload={"status": status, "detail": detail},
        )

    transcript = extract_transcript_text(job)
    if not transcript:
        raise TranscriptionApiError(f"Job {job_id} completado sin transcript util", payload=job)
    return transcript


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


def validate_and_collect_videos(
    urls: List[str],
    progress_callback: Optional[TranscriptionProgressCallback] = None,
) -> Tuple[List[VideoRecord], List[RejectedVideo], List[str]]:
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

    normalized_urls = [raw_url.strip() for raw_url in urls if raw_url and raw_url.strip()]
    total_videos = len(normalized_urls)

    for idx, url in enumerate(normalized_urls, start=1):
        _emit_progress(
            progress_callback,
            {
                "video_index": idx,
                "total_videos": total_videos,
                "phase": "queued",
                "status": "queued",
                "progress_percent": 0,
                "next_poll_after_seconds": 1,
                "eta_seconds": None,
                "message": "Validando metadata del video...",
                "url": url,
                "title": "",
                "job_id": "",
            },
        )

        video_id = extract_youtube_id(url)
        if not video_id:
            rejected.append(RejectedVideo(url=url, reason="URL no parece ser un video válido de YouTube."))
            continue

        transcript = ""

        # 1. Intentar metadata para validacion de duracion
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

        # 2. Obtener transcript desde cluster local
        try:
            duration_for_job = duration_seconds if duration_seconds > 0 else None
            transcript = _fetch_transcript_from_cluster_with_progress(
                url=url,
                duration_seconds=duration_for_job,
                progress_callback=progress_callback,
                video_index=idx,
                total_videos=total_videos,
                title=title,
            )
        except Exception as cluster_exc:
            if _ENABLE_LEGACY_YOUTUBE_FALLBACK:
                try:
                    transcript = _run_with_timeout(_fetch_transcript, (video_id,), timeout_seconds=25)
                    warnings.append(
                        f"{title}: se uso fallback local youtube-transcript-api por error del cluster: {cluster_exc}"
                    )
                except Exception as fallback_exc:
                    rejected.append(
                        RejectedVideo(
                            url=url,
                            reason=(
                                "No se pudo obtener transcript via cluster local ni fallback. "
                                f"Cluster: {cluster_exc} | Fallback: {fallback_exc}"
                            ),
                            duration_seconds=duration_seconds if duration_seconds > 0 else None,
                        )
                    )
                    continue
            else:
                rejected.append(
                    RejectedVideo(
                        url=url,
                        reason=f"No se pudo obtener transcript via API local: {cluster_exc}",
                        duration_seconds=duration_seconds if duration_seconds > 0 else None,
                    )
                )
                continue

        accepted.append(
            VideoRecord(
                url=url,
                video_id=video_id,
                title=title,
                duration_seconds=duration_seconds,
                transcript=transcript,
            )
        )

        _emit_progress(
            progress_callback,
            {
                "video_index": idx,
                "total_videos": total_videos,
                "phase": "completed",
                "status": "completed",
                "progress_percent": 100,
                "next_poll_after_seconds": 0,
                "eta_seconds": 0,
                "message": "Transcripcion completada para este video.",
                "url": url,
                "title": title,
                "job_id": "",
            },
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
