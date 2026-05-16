"""
Cliente HTTP para API local de transcripciones (Next.js cluster admin facade).

Base URL por defecto: http://127.0.0.1:3001
Auth: cookie access_token
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
ACTIVE_PHASES = {"queued", "assigned", "downloading", "transcribing"}


def _runtime_from_status(status: str) -> Dict[str, Any]:
    phase = status if status in (ACTIVE_PHASES | TERMINAL_STATUSES) else "queued"
    progress_map = {
        "queued": 5,
        "assigned": 15,
        "downloading": 35,
        "transcribing": 75,
        "completed": 100,
        "failed": 100,
        "cancelled": 100,
    }
    next_poll_map = {
        "queued": 5,
        "assigned": 4,
        "downloading": 3,
        "transcribing": 2,
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
    }
    message_map = {
        "queued": "Job en cola",
        "assigned": "Job asignado a nodo",
        "downloading": "Descargando contenido",
        "transcribing": "Transcribiendo audio",
        "completed": "Transcripcion completada",
        "failed": "Transcripcion fallida",
        "cancelled": "Transcripcion cancelada",
    }
    return {
        "phase": phase,
        "progress_percent": progress_map.get(phase, 0),
        "next_poll_after_seconds": next_poll_map.get(phase, 5),
        "eta_seconds": None,
        "message": message_map.get(phase, "Procesando"),
    }


def _normalize_runtime(runtime: Any, status: str) -> Dict[str, Any]:
    fallback = _runtime_from_status(status)
    if not isinstance(runtime, dict):
        return fallback

    normalized = dict(runtime)
    normalized.setdefault("phase", fallback["phase"])
    normalized.setdefault("progress_percent", fallback["progress_percent"])
    normalized.setdefault("next_poll_after_seconds", fallback["next_poll_after_seconds"])
    normalized.setdefault("eta_seconds", fallback["eta_seconds"])
    normalized.setdefault("message", fallback["message"])

    try:
        normalized["progress_percent"] = int(normalized["progress_percent"])
    except Exception:
        normalized["progress_percent"] = fallback["progress_percent"]

    normalized["progress_percent"] = max(0, min(100, normalized["progress_percent"]))
    return normalized


def _augment_job_runtime(job: Any) -> Any:
    if not isinstance(job, dict):
        return job
    status = str(job.get("status", "")).lower()
    result = dict(job)
    result["runtime"] = _normalize_runtime(result.get("runtime"), status)
    return result


def _augment_list_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(payload)
    jobs = result.get("jobs")
    if isinstance(jobs, list):
        jobs_augmented = [_augment_job_runtime(job) for job in jobs]
        result["jobs"] = jobs_augmented
        if not isinstance(result.get("meta"), dict):
            active = 0
            for job in jobs_augmented:
                if isinstance(job, dict):
                    runtime = job.get("runtime")
                    phase = runtime.get("phase") if isinstance(runtime, dict) else ""
                    if str(phase).lower() in ACTIVE_PHASES:
                        active += 1
            result["meta"] = {"total": len(jobs_augmented), "active": active}
    return result


class TranscriptionApiError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


@dataclass
class TranscriptionApiClient:
    base_url: str = "http://127.0.0.1:3001"
    access_token: str = "test"
    timeout_seconds: int = 20

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.session = requests.Session()
        if self.access_token:
            self.session.cookies.set("access_token", self.access_token)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        expected_statuses: tuple[int, ...] = (200,),
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload, _, status_code = self._request_json_with_headers(
            method,
            path,
            expected_statuses=expected_statuses,
            json_body=json_body,
        )
        payload.setdefault("http_status", status_code)
        return payload

    def _request_json_with_headers(
        self,
        method: str,
        path: str,
        *,
        expected_statuses: tuple[int, ...] = (200,),
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, str], int]:
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=json_body,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise TranscriptionApiError(f"Error de conectividad hacia {url}: {exc}") from exc

        try:
            payload = response.json()
        except ValueError:
            payload = {"detail": response.text}

        if response.status_code not in expected_statuses:
            raise TranscriptionApiError(
                f"HTTP {response.status_code} en {method} {path}",
                status_code=response.status_code,
                payload=payload,
            )

        headers = {k.lower(): v for k, v in response.headers.items()}
        if not isinstance(payload, dict):
            result = {"data": payload}
            result.setdefault("http_status", response.status_code)
            return result, headers, response.status_code
        payload.setdefault("http_status", response.status_code)
        return payload, headers, response.status_code

    # Jobs API
    def list_jobs(self) -> Dict[str, Any]:
        payload, headers, _ = self._request_json_with_headers("GET", "/api/transcriptions")
        result = _augment_list_payload(payload)
        retry_after = headers.get("retry-after")
        if retry_after is not None:
            result["retry_after_seconds"] = retry_after
        return result

    def create_job(
        self,
        *,
        url: str,
        mode: str = "async",
        language: str = "auto",
        model_profile: str = "balanced-es",
        duration_seconds: Optional[int] = None,
        duration: Optional[int] = None,
        paragraph_strategy: str = "pause_based",
        webhook_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "url": url,
            "mode": mode,
            "language": language,
            "model_profile": model_profile,
            "paragraph_strategy": paragraph_strategy,
        }
        effective_duration = duration_seconds if duration_seconds is not None else duration
        if effective_duration is not None and effective_duration > 0:
            body["duration_seconds"] = effective_duration
        if webhook_url:
            body["webhook_url"] = webhook_url

        # create job can return 202 async, 200 sync success, 422 sync terminal fail
        payload, headers, _ = self._request_json_with_headers(
            "POST",
            "/api/transcriptions",
            expected_statuses=(200, 202, 422, 400),
            json_body=body,
        )
        result = dict(payload)
        result["runtime"] = _normalize_runtime(result.get("runtime"), str(result.get("status", "")).lower())
        retry_after = headers.get("retry-after")
        if retry_after is not None:
            result["retry_after_seconds"] = retry_after
        return result

    def get_job(self, job_id: str) -> Dict[str, Any]:
        payload, headers, _ = self._request_json_with_headers("GET", f"/api/transcriptions/{job_id}")
        result = _augment_job_runtime(payload)
        retry_after = headers.get("retry-after")
        if retry_after is not None:
            result["retry_after_seconds"] = retry_after
        return result

    def cancel_job(self, job_id: str) -> Dict[str, Any]:
        return self._request_json("DELETE", f"/api/transcriptions/{job_id}")

    # Admin API
    def get_nodes(self) -> Dict[str, Any]:
        return self._request_json("GET", "/api/admin/transcription/nodes")

    def patch_node_capacity(self, node_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request_json(
            "PATCH",
            f"/api/admin/transcription/nodes/{node_name}/capacity",
            json_body=payload,
        )

    def patch_node_profile(self, node_name: str, model_profile: str) -> Dict[str, Any]:
        return self._request_json(
            "PATCH",
            f"/api/admin/transcription/nodes/{node_name}/profile",
            json_body={"model_profile": model_profile},
        )

    def get_model_profiles(self) -> Dict[str, Any]:
        return self._request_json("GET", "/api/admin/transcription/model-profiles")

    def put_model_profile(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request_json(
            "PUT",
            f"/api/admin/transcription/model-profiles/{name}",
            json_body=payload,
        )

    def get_scheduler_policy(self) -> Dict[str, Any]:
        return self._request_json("GET", "/api/admin/transcription/scheduler/policy")

    def patch_scheduler_policy(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request_json(
            "PATCH",
            "/api/admin/transcription/scheduler/policy",
            json_body=payload,
        )

    def get_queue(self) -> Dict[str, Any]:
        return self._request_json("GET", "/api/admin/transcription/queue")

    def rebalance_queue(self, reason: str = "manual_admin", dry_run: bool = False) -> Dict[str, Any]:
        return self._request_json(
            "POST",
            "/api/admin/transcription/queue/rebalance",
            json_body={"reason": reason, "dry_run": dry_run},
        )

    # Helpers
    def wait_for_terminal_status(
        self,
        job_id: str,
        *,
        timeout_seconds: int = 300,
        poll_interval_seconds: int = 3,
    ) -> Dict[str, Any]:
        started = time.time()
        while True:
            job = self.get_job(job_id)
            status = str(job.get("status", "")).lower()
            if status in TERMINAL_STATUSES:
                return job
            if time.time() - started > timeout_seconds:
                raise TranscriptionApiError(
                    f"Timeout esperando estado terminal para job {job_id}",
                    payload={"last_status": status},
                )
            time.sleep(poll_interval_seconds)


def extract_transcript_text(job_payload: Dict[str, Any]) -> str:
    transcript = job_payload.get("transcript")
    if isinstance(transcript, dict):
        full_text = transcript.get("full_text")
        if isinstance(full_text, str) and full_text.strip():
            return full_text.strip()

        paragraphs = transcript.get("paragraphs")
        if isinstance(paragraphs, list):
            merged: List[str] = []
            for item in paragraphs:
                if isinstance(item, dict):
                    txt = item.get("text") or item.get("content") or ""
                else:
                    txt = str(item)
                if txt and str(txt).strip():
                    merged.append(str(txt).strip())
            if merged:
                return "\n\n".join(merged)

    # Compatibilidad adicional si backend devuelve text plano.
    for key in ("full_text", "text", "transcription"):
        val = job_payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    return ""
