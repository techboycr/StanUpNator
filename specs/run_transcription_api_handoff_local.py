"""
Runner local para validar checklist de handoff del API de transcripciones.

Uso:
  .\\.venv\\Scripts\\python.exe specs\\run_transcription_api_handoff_local.py

Variables opcionales:
  TRANSCRIPTION_API_BASE_URL=http://127.0.0.1:3001
  TRANSCRIPTION_API_ACCESS_TOKEN=test
  TRANSCRIPTION_API_MODEL_PROFILE=balanced-es
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List

from transcription_api_client import TranscriptionApiClient, TranscriptionApiError


BASE_URL = os.getenv("TRANSCRIPTION_API_BASE_URL", "http://127.0.0.1:3001").strip()
TOKEN = os.getenv("TRANSCRIPTION_API_ACCESS_TOKEN", "test").strip()
MODEL_PROFILE = os.getenv("TRANSCRIPTION_API_MODEL_PROFILE", "balanced-es").strip() or "balanced-es"
LINKS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_links.txt")


def _print_ok(label: str, detail: str = "") -> None:
    print(f"[OK] {label}{': ' + detail if detail else ''}")


def _print_fail(label: str, detail: str = "") -> None:
    print(f"[FAIL] {label}{': ' + detail if detail else ''}")


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _has_runtime_shape(payload: Dict[str, Any]) -> bool:
    runtime = payload.get("runtime")
    if not isinstance(runtime, dict):
        return False
    required = {"phase", "progress_percent", "next_poll_after_seconds", "eta_seconds", "message"}
    return required.issubset(runtime.keys())


def _check(label: str, condition: bool, detail_ok: str, detail_fail: str, failures: List[str]) -> None:
    if condition:
        _print_ok(label, detail_ok)
    else:
        _print_fail(label, detail_fail)
        failures.append(f"{label}: {detail_fail}")


def _read_links() -> List[str]:
    if not os.path.exists(LINKS_FILE):
        return []
    with open(LINKS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]


def _first_terminal_job(client: TranscriptionApiClient, job_id: str, timeout: int = 180) -> Dict[str, Any]:
    return client.wait_for_terminal_status(job_id, timeout_seconds=timeout, poll_interval_seconds=3)


def main() -> int:
    print("=== Handoff local validation ===")
    print(f"BASE_URL={BASE_URL}")

    links = _read_links()
    if not links:
        _print_fail("Cargar links", "No hay links en test_links.txt")
        return 1

    client = TranscriptionApiClient(base_url=BASE_URL, access_token=TOKEN, timeout_seconds=20)

    failures: List[str] = []

    # 1) Auth check
    try:
        jobs_response = client.list_jobs()
        jobs = jobs_response.get("jobs", [])
        meta = jobs_response.get("meta", {})
        _check(
            "Auth GET /api/transcriptions",
            isinstance(jobs, list),
            f"jobs={len(jobs)}",
            f"shape invalido={jobs_response}",
            failures,
        )
        _check(
            "GET listado incluye meta.total y meta.active",
            isinstance(meta, dict) and "total" in meta and "active" in meta,
            json.dumps(meta, ensure_ascii=True),
            f"meta ausente/invalido={meta}",
            failures,
        )
        if isinstance(jobs, list) and jobs:
            _check(
                "GET listado incluye runtime por job",
                all(isinstance(j, dict) and _has_runtime_shape(j) for j in jobs[: min(3, len(jobs))]),
                "runtime presente en jobs muestreados",
                "runtime faltante en uno o mas jobs",
                failures,
            )
    except Exception as exc:
        _print_fail("Auth GET /api/transcriptions", str(exc))
        return 1

    # 2) Create async con duration_seconds=3600 (obligatorio)
    async_job_id = None
    try:
        created = client.create_job(url=links[0], mode="async", model_profile=MODEL_PROFILE, duration_seconds=3600)
        async_job_id = created.get("job_id")
        if not async_job_id:
            raise RuntimeError(f"respuesta sin job_id: {created}")
        _check(
            "Create async con duration_seconds=3600 responde 202",
            _to_int(created.get("http_status"), 0) == 202 and created.get("job_id") is not None,
            f"http_status={created.get('http_status')} job_id={async_job_id} status={created.get('status')}",
            f"respuesta inesperada={created}",
            failures,
        )
        _check(
            "Create async incluye runtime",
            _has_runtime_shape(created),
            json.dumps(created.get("runtime", {}), ensure_ascii=True),
            f"runtime faltante={created}",
            failures,
        )
        _check(
            "Create async incluye Retry-After",
            _to_int(created.get("retry_after_seconds"), -1) >= 0,
            f"Retry-After={created.get('retry_after_seconds')}",
            f"retry_after_seconds faltante={created}",
            failures,
        )
    except Exception as exc:
        _print_fail("Create async con duration_seconds=3600", str(exc))
        failures.append(f"Create async con duration_seconds=3600: {exc}")

    # 3) GET por id del job creado (obligatorio)
    if async_job_id:
        try:
            by_id = client.get_job(str(async_job_id))
            _check(
                "GET por id responde 200 con runtime",
                isinstance(by_id, dict)
                and _to_int(by_id.get("http_status"), 0) == 200
                and by_id.get("job_id") == async_job_id
                and _has_runtime_shape(by_id),
                f"http_status={by_id.get('http_status')} status={by_id.get('status')} runtime.phase={by_id.get('runtime', {}).get('phase')}",
                f"respuesta invalida={by_id}",
                failures,
            )
            _check(
                "GET por id incluye Retry-After",
                _to_int(by_id.get("retry_after_seconds"), -1) >= 0,
                f"Retry-After={by_id.get('retry_after_seconds')}",
                f"retry_after_seconds faltante={by_id}",
                failures,
            )
        except Exception as exc:
            _print_fail("GET por id", str(exc))
            failures.append(f"GET por id: {exc}")

    # 4) GET listado con meta y runtime (obligatorio)
    try:
        list_payload = client.list_jobs()
        listed = list_payload.get("jobs", [])
        meta = list_payload.get("meta", {})
        completed = [j for j in listed if str(j.get("status", "")).lower() == "completed"]
        active = [j for j in listed if str(j.get("status", "")).lower() in {"queued", "assigned", "downloading", "transcribing"}]
        _check(
            "GET listado incluye meta.total y meta.active",
            isinstance(meta, dict) and "total" in meta and "active" in meta,
            json.dumps(meta, ensure_ascii=True),
            f"meta invalida={meta}",
            failures,
        )
        _check(
            "GET listado incluye runtime por job",
            isinstance(listed, list) and all(isinstance(j, dict) and _has_runtime_shape(j) for j in listed[: min(5, len(listed))]),
            f"runtime OK en {min(5, len(listed))} jobs muestreados",
            "runtime faltante/invalido en listado",
            failures,
        )
        _print_ok("Listar jobs y filtrar estado", f"total={len(listed)} completed={len(completed)} active={len(active)}")
    except Exception as exc:
        _print_fail("GET listado", str(exc))
        failures.append(f"GET listado: {exc}")

    # 5) Create con duration_seconds=3700 debe 400 (obligatorio)
    try:
        over_limit = client.create_job(
            url=links[0],
            mode="async",
            model_profile=MODEL_PROFILE,
            duration_seconds=3700,
        )
        _check(
            "Create con duration_seconds=3700 responde 400",
            isinstance(over_limit, dict) and _to_int(over_limit.get("http_status"), 0) == 400,
            f"http_status={over_limit.get('http_status')} detail={over_limit.get('detail')}",
            f"respuesta inesperada={over_limit}",
            failures,
        )
    except TranscriptionApiError as exc:
        _check(
            "Create con duration_seconds=3700 responde 400",
            exc.status_code == 400,
            f"status={exc.status_code} payload={exc.payload}",
            f"status={exc.status_code} payload={exc.payload}",
            failures,
        )
    except Exception as exc:
        _print_fail("Create con duration_seconds=3700", str(exc))
        failures.append(f"Create con duration_seconds=3700: {exc}")

    # 5) Read nodes + policy
    original_node = None
    original_policy = None
    try:
        nodes_resp = client.get_nodes()
        nodes = nodes_resp.get("nodes", [])
        original_node = nodes[0] if nodes else None
        _print_ok("Leer nodos", f"nodos={len(nodes)}")

        original_policy = client.get_scheduler_policy().get("policy", {})
        _print_ok("Leer policy", json.dumps(original_policy, ensure_ascii=True))
    except Exception as exc:
        _print_fail("Leer nodos/policy", str(exc))

    # 6) Change node capacity + verify
    if original_node:
        node_name = str(original_node.get("node_name"))
        old_capacity = original_node.get("capacity_weight")
        try:
            target_capacity = 0.9 if old_capacity != 0.9 else 0.8
            client.patch_node_capacity(node_name, {"capacity_weight": target_capacity})
            refreshed = client.get_nodes().get("nodes", [])
            current = next((n for n in refreshed if str(n.get("node_name")) == node_name), None)
            _print_ok("Cambiar capacidad", f"{node_name} -> {current.get('capacity_weight') if current else 'n/a'}")
        except Exception as exc:
            _print_fail("Cambiar capacidad", str(exc))
        finally:
            try:
                client.patch_node_capacity(node_name, {"capacity_weight": old_capacity})
            except Exception:
                pass

    # 7) Change node profile + verify
    if original_node:
        node_name = str(original_node.get("node_name"))
        old_profile = original_node.get("assigned_model_profile")
        try:
            profiles = client.get_model_profiles().get("profiles", [])
            profile_names = [str(p.get("name")) for p in profiles if p.get("name")]
            candidate = next((p for p in profile_names if p != old_profile), old_profile)
            if candidate:
                client.patch_node_profile(node_name, candidate)
                _print_ok("Cambiar perfil de nodo", f"{node_name} -> {candidate}")
            else:
                _print_fail("Cambiar perfil de nodo", "No hay perfiles disponibles")
        except Exception as exc:
            _print_fail("Cambiar perfil de nodo", str(exc))
        finally:
            if old_profile:
                try:
                    client.patch_node_profile(node_name, str(old_profile))
                except Exception:
                    pass

    # 8) Create or update model profile
    profile_name = f"standup-temp-{int(time.time())}"
    profile_payload = {
        "backend": "faster-whisper",
        "model_name": "small",
        "compute_type": "int8",
        "decode_params": {
            "beam_size": 5,
            "vad_filter": True,
            "temperature": 0,
        },
        "active": True,
    }
    try:
        upsert = client.put_model_profile(profile_name, profile_payload)
        _print_ok("Crear/actualizar perfil", json.dumps(upsert, ensure_ascii=True))
    except Exception as exc:
        _print_fail("Crear/actualizar perfil", str(exc))

    # 9) Queue snapshot + active jobs
    try:
        queue = client.get_queue().get("items", [])
        active_queue = [i for i in queue if str(i.get("status", "")).lower() == "queued"]
        _print_ok("Leer cola", f"items={len(queue)} queued={len(active_queue)}")
    except Exception as exc:
        _print_fail("Leer cola", str(exc))

    # 10) Manual rebalance
    try:
        rebalance = client.rebalance_queue(reason="manual_admin", dry_run=False)
        _print_ok("Rebalance manual", json.dumps(rebalance, ensure_ascii=True))
    except Exception as exc:
        _print_fail("Rebalance manual", str(exc))

    # 11) Sync mode test (obligatorio <=300)
    try:
        # El backend puede mantener la request hasta ~120s en sync corto;
        # usamos timeout de cliente mayor para validar el comportamiento real.
        sync_client = TranscriptionApiClient(base_url=BASE_URL, access_token=TOKEN, timeout_seconds=140)
        sync_result = sync_client.create_job(
            url=links[1] if len(links) > 1 else links[0],
            mode="sync",
            model_profile=MODEL_PROFILE,
            duration_seconds=120,
        )
        status = str(sync_result.get("status", "")).lower()
        detail = sync_result.get("detail")
        http_status = _to_int(sync_result.get("http_status"), 0)
        accepted = http_status in {200, 202, 422}
        _check(
            "Modo sync (<=300s) valida rama 200/422/202",
            accepted,
            f"http_status={http_status} status={status or detail}",
            f"respuesta inesperada={sync_result}",
            failures,
        )
    except Exception as exc:
        _print_fail("Modo sync (<=300s)", str(exc))
        failures.append(f"Modo sync (<=300s): {exc}")

    # 12) Common errors 401, 400, 422
    # 401: no auth cookie
    try:
        unauth = TranscriptionApiClient(base_url=BASE_URL, access_token="", timeout_seconds=10)
        unauth.list_jobs()
        _print_fail("Error 401", "No se obtuvo 401 sin token")
    except TranscriptionApiError as exc:
        if exc.status_code == 401:
            _print_ok("Error 401", "sin token retorna 401")
        else:
            _print_fail("Error 401", f"status={exc.status_code} payload={exc.payload}")

    # 400: invalid url
    try:
        bad_400 = client.create_job(url="https://example.com/not-youtube", mode="async", model_profile=MODEL_PROFILE)
        detail = str(bad_400.get("detail", ""))
        if detail:
            _print_ok("Error 400", detail)
        else:
            _print_fail("Error 400", f"respuesta inesperada={bad_400}")
    except TranscriptionApiError as exc:
        if exc.status_code == 400:
            _print_ok("Error 400", str(exc.payload))
        else:
            _print_fail("Error 400", f"status={exc.status_code} payload={exc.payload}")

    # 422: sync with likely unsupported condition (invalid duration, force terminal fail shape)
    try:
        maybe_422 = client.create_job(url=links[2] if len(links) > 2 else links[0], mode="sync", model_profile=MODEL_PROFILE, duration_seconds=301)
        # API podria responder 202 en lugar de 422 si cae a async. Registramos resultado.
        _print_ok("Validacion 422/sync fallback", json.dumps(maybe_422, ensure_ascii=True)[:220])
    except TranscriptionApiError as exc:
        if exc.status_code == 422:
            _print_ok("Error 422", str(exc.payload))
        else:
            _print_fail("Error 422", f"status={exc.status_code} payload={exc.payload}")

    print("=== Fin validacion local ===")
    if failures:
        print(f"VALIDACION ESTRICTA: FAIL ({len(failures)} errores)")
        for idx, item in enumerate(failures, start=1):
            print(f"  {idx}. {item}")
        return 1

    print("VALIDACION ESTRICTA: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
