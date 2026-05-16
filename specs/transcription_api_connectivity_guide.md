# Guia de Conectividad API de Transcripciones (Cluster Admin)

## 1. Objetivo
Este documento describe como consumir el API de transcripciones ya implementado en el panel admin para que otra sesion de GitHub Copilot pueda desarrollar la conectividad (cliente, integracion backend, QA E2E).

Alcance:
- Endpoints reales disponibles hoy en Next.js (App Router).
- Formato de requests/responses esperado.
- Flujo recomendado para integracion.
- Ejemplos listos para copiar (curl y fetch).

## 2. Base URL y contexto
Entorno local dev:
- `http://127.0.0.1:3001`

Rutas publicadas por el panel admin:
- API jobs: `/api/transcriptions`
- API admin: `/api/admin/transcription/*`

Importante:
- Estas rutas son del servidor Next.js, no del servicio TensorLab ni del cluster_admin_api directo.

## 3. Autenticacion
Todos los endpoints de este modulo requieren cookie `access_token`.

En codigo de rutas:
- Se valida `cookies().get("access_token")`.
- Si no existe: `401` con `{ "detail": "Not authenticated" }`.

Para pruebas locales:
- Se puede usar `Cookie: access_token=test`.

Ejemplo:
```bash
-H 'Cookie: access_token=test'
```

## 4. API de Jobs de Transcripcion

### 4.1 Crear job
Endpoint:
- `POST /api/transcriptions`

Body:
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "mode": "async",
  "language": "auto",
  "model_profile": "balanced-es",
  "webhook_url": "https://cliente.example/webhook",
  "paragraph_strategy": "pause_based",
  "duration_seconds": 3600
}
```

Campos:
- `url` (requerido): debe ser YouTube (`youtube.com` o `youtu.be`).
- `mode` (opcional): `async` o `sync`.
- `duration_seconds` (opcional): recomendado para tests deterministas.
- `duration` (opcional): alias compatible de `duration_seconds`.

Restriccion de duracion:
- Maximo soportado: `3600` segundos (60 minutos).
- Si `duration_seconds` o `duration` es mayor a `3600`, el endpoint debe responder `400` con mensaje claro de validacion.

Respuestas:
- `202 Accepted`:
```json
{
  "job_id": "job_xxx",
  "status": "queued|assigned|...",
  "queue_position": 0,
  "video_id": "dQw4w9WgXcQ",
  "estimated_duration_seconds": 3600,
  "status_url": "/api/transcriptions/job_xxx",
  "runtime": {
    "phase": "queued|assigned|downloading|transcribing|completed|failed|cancelled",
    "progress_percent": 0,
    "next_poll_after_seconds": 3,
    "eta_seconds": null,
    "message": "Job en cola"
  }
}
```
- Header requerido: `Retry-After` (segundos sugeridos para siguiente polling).
- `200 OK` en modo `sync` si termina bien dentro de la ventana de polling.
- `422` en modo `sync` si termina en `failed` o `cancelled`.
- `400` para validaciones (ej. URL invalida o no YouTube).

Comportamiento `sync`:
- Si `mode=sync` y duracion <= 300s, el endpoint hace polling hasta 120s.
- Si completa: responde job final (`200`).
- Si falla/cancela: responde job final (`422`).
- Si no termina en esa ventana: cae al flujo async y responde `202`.

### 4.2 Listar jobs
Endpoint:
- `GET /api/transcriptions`

Respuesta:
```json
{
  "jobs": [
    {
      "job_id": "job_xxx",
      "status": "queued|assigned|downloading|transcribing|completed|failed|cancelled",
      "assigned_node": "z13_master|geekom_R9_AI|hp_pavilion|null",
      "assigned_profile": "balanced-es|null",
      "video_duration_seconds": 3600,
      "estimated_seconds": 1080,
      "queue_position": 0,
      "status_detail": {
        "reason": "fifo_capacity_fit",
        "remote_status_path": "/tmp/...",
        "remote_result_path": "/tmp/...",
        "remote_log_path": "/tmp/...",
        "remote_pid_path": "/tmp/...",
        "remote_script_path": "/tmp/...",
        "remote_error": "..."
      },
      "transcript": {
        "full_text": "",
        "paragraphs": []
      },
      "runtime": {
        "phase": "queued",
        "progress_percent": 5,
        "next_poll_after_seconds": 5,
        "eta_seconds": null,
        "message": "Job en cola"
      }
    }
  ],
  "meta": {
    "total": 1,
    "active": 1
  }
}
```

### 4.3 Consultar job por id
Endpoint:
- `GET /api/transcriptions/{id}`

Respuesta:
- `200` con objeto job.
- `404` si no existe.

Job debe incluir `runtime` con los campos:
- `phase`
- `progress_percent`
- `next_poll_after_seconds`
- `eta_seconds`
- `message`

Header recomendado/operativo:
- `Retry-After`: tomar este valor para guiar polling en cliente.

### 4.4 Cancelar job
Endpoint:
- `DELETE /api/transcriptions/{id}`

Respuesta:
- `200` con job actualizado (`cancelled`) si aplica.
- `400` si no se puede cancelar (por ejemplo, ya terminal).

## 5. API Admin de Scheduling y Nodos

### 5.1 Obtener nodos
Endpoint:
- `GET /api/admin/transcription/nodes`

Respuesta:
```json
{
  "nodes": [
    {
      "node_name": "z13_master",
      "enabled": true,
      "priority_rank": 1,
      "capacity_weight": 1,
      "max_concurrent_jobs": 1,
      "assigned_model_profile": "balanced-es",
      "running_jobs": 0,
      "queue_assigned": 0,
      "cpu_utilization_percent": 0,
      "health": "healthy",
      "heartbeat_at": "2026-05-13T07:01:22.685Z"
    }
  ]
}
```

### 5.2 Actualizar capacidad de nodo
Endpoint:
- `PATCH /api/admin/transcription/nodes/{node}/capacity`

Body (cualquier subconjunto):
```json
{
  "enabled": true,
  "priority_rank": 2,
  "capacity_weight": 0.75,
  "max_concurrent_jobs": 1
}
```

Respuesta:
```json
{
  "node": "geekom_R9_AI",
  "updated": {
    "capacity_weight": 0.75
  }
}
```

### 5.3 Cambiar perfil de modelo de un nodo
Endpoint:
- `PATCH /api/admin/transcription/nodes/{node}/profile`

Body:
```json
{
  "model_profile": "balanced-es"
}
```

Respuesta:
```json
{
  "node": "hp_pavilion",
  "previous_profile": "quality-es",
  "current_profile": "balanced-es"
}
```

### 5.4 Listar perfiles
Endpoint:
- `GET /api/admin/transcription/model-profiles`

Respuesta:
```json
{
  "profiles": [
    {
      "name": "balanced-es",
      "backend": "faster-whisper",
      "model_name": "small",
      "compute_type": "int8",
      "decode_params": {
        "beam_size": 5,
        "vad_filter": true,
        "temperature": 0
      },
      "active": true,
      "created_at": "...",
      "updated_at": "..."
    }
  ]
}
```

### 5.5 Crear/actualizar perfil
Endpoint:
- `PUT /api/admin/transcription/model-profiles/{name}`

Body:
```json
{
  "backend": "faster-whisper",
  "model_name": "small",
  "compute_type": "int8",
  "decode_params": {
    "beam_size": 5,
    "vad_filter": true,
    "temperature": 0
  },
  "active": true
}
```

Respuesta:
```json
{
  "profile": "balanced-es",
  "created_or_updated": "created|updated"
}
```

### 5.6 Leer policy del scheduler
Endpoint:
- `GET /api/admin/transcription/scheduler/policy`

Respuesta:
```json
{
  "policy": "fifo_capacity_fit",
  "window_size": 15,
  "strict_fifo": false,
  "allow_rebalance": true,
  "updated_at": "..."
}
```

### 5.7 Actualizar policy del scheduler
Endpoint:
- `PATCH /api/admin/transcription/scheduler/policy`

Body (subconjunto):
```json
{
  "window_size": 15,
  "strict_fifo": false,
  "allow_rebalance": true
}
```

Respuesta:
```json
{
  "policy": {
    "policy": "fifo_capacity_fit",
    "window_size": 15,
    "strict_fifo": false,
    "allow_rebalance": true,
    "updated_at": "..."
  }
}
```

### 5.8 Snapshot de cola
Endpoint:
- `GET /api/admin/transcription/queue`

Respuesta:
```json
{
  "items": [
    {
      "job_id": "job_xxx",
      "position": 0,
      "queue_position": 0,
      "status": "completed",
      "video_duration_seconds": 3600,
      "estimated_seconds": 1080,
      "assigned_node": "z13_master",
      "assigned_profile": "balanced-es",
      "created_at": "..."
    }
  ],
  "total": 16,
  "head_job_id": null
}
```

Nota:
- `items` incluye jobs historicos y no solo `queued`.
- Para cola activa, filtrar por `status === "queued"`.

### 5.9 Rebalance manual
Endpoint:
- `POST /api/admin/transcription/queue/rebalance`

Body:
```json
{
  "reason": "manual_admin",
  "dry_run": false
}
```

`reason` permitido:
- `node_profile_change`
- `node_down`
- `manual_admin`

Respuesta:
```json
{
  "dry_run": false,
  "evaluated_jobs": 0,
  "reassigned_jobs": 0,
  "changes": []
}
```

## 6. Flujo recomendado de conectividad para otra sesion
1. Verificar auth con `GET /api/transcriptions`.
2. Crear job async con URL YouTube valida.
3. Polling cada 2-5s de `GET /api/transcriptions/{id}`.
4. Leer nodos y policy para panel operativo:
   - `GET /api/admin/transcription/nodes`
   - `GET /api/admin/transcription/scheduler/policy`
5. Leer cola para monitoreo:
   - `GET /api/admin/transcription/queue`
6. Integrar operaciones admin:
   - patch capacidad
   - patch profile
   - rebalance

## 7. Ejemplos curl rapidos

### 7.1 Crear job async
```bash
curl -sS -X POST 'http://127.0.0.1:3001/api/transcriptions' \
  -H 'Content-Type: application/json' \
  -H 'Cookie: access_token=test' \
  -d '{
    "url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "mode":"async",
    "model_profile":"balanced-es",
    "duration_seconds":600
  }'
```

### 7.2 Obtener nodos
```bash
curl -sS 'http://127.0.0.1:3001/api/admin/transcription/nodes' \
  -H 'Cookie: access_token=test'
```

### 7.3 Cambiar capacidad de nodo
```bash
curl -sS -X PATCH 'http://127.0.0.1:3001/api/admin/transcription/nodes/geekom_R9_AI/capacity' \
  -H 'Content-Type: application/json' \
  -H 'Cookie: access_token=test' \
  -d '{"capacity_weight":0.75,"max_concurrent_jobs":1}'
```

### 7.4 Cambiar policy
```bash
curl -sS -X PATCH 'http://127.0.0.1:3001/api/admin/transcription/scheduler/policy' \
  -H 'Content-Type: application/json' \
  -H 'Cookie: access_token=test' \
  -d '{"window_size":15,"strict_fifo":false,"allow_rebalance":true}'
```

## 8. Errores comunes y mitigacion
- 401 Not authenticated:
  - Falta cookie `access_token`.
- 400 `url es requerido`:
  - Body sin `url`.
- 400 `url debe pertenecer a YouTube`:
  - URL no es `youtube.com` o `youtu.be`.
- Cola vacia inesperada despues de reset manual:
  - Si se edita JSON de estado/jobs con shape invalido, el sistema ahora se auto-recupera a defaults.

## 9. Archivos fuente de referencia
- Rutas jobs: `nextjs_admin_app/app/api/transcriptions/route.ts`
- Ruta job by id: `nextjs_admin_app/app/api/transcriptions/[id]/route.ts`
- Rutas admin transcriptions: `nextjs_admin_app/app/api/admin/transcription/*`
- Scheduler y logica runtime: `nextjs_admin_app/lib/transcription-admin.ts`
- Cliente frontend actual: `nextjs_admin_app/lib/api.ts`
- Tipos TS usados por UI: `nextjs_admin_app/lib/types.ts`

## 10. Estado operativo validado (resumen)
Validado en esta rama:
- Asignacion inicial esperada 3600/2700/1800 -> z13_master/geekom_R9_AI/hp_pavilion.
- Endpoints admin respondiendo correctamente.
- Modo sync corto devolviendo terminal correcto (`200` completado; `422` si terminal no exitoso).
