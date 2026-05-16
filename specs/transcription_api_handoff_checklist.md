# Handoff Checklist — Integración API Transcripciones (Cluster Admin)

## 1. Objetivo
Implementar cliente o integración backend para el API de transcripciones del cluster, usando los endpoints Next.js ya operativos.

## 2. Endpoints clave
- Crear job: `POST /api/transcriptions`
- Listar jobs: `GET /api/transcriptions`
- Consultar job: `GET /api/transcriptions/{id}`
- Cancelar job: `DELETE /api/transcriptions/{id}`
- Nodos: `GET /api/admin/transcription/nodes`
- Cambiar capacidad: `PATCH /api/admin/transcription/nodes/{node}/capacity`
- Cambiar perfil: `PATCH /api/admin/transcription/nodes/{node}/profile`
- Perfiles: `GET /api/admin/transcription/model-profiles`
- Crear/actualizar perfil: `PUT /api/admin/transcription/model-profiles/{name}`
- Policy: `GET`/`PATCH /api/admin/transcription/scheduler/policy`
- Cola: `GET /api/admin/transcription/queue`
- Rebalance: `POST /api/admin/transcription/queue/rebalance`

## 3. Auth
- Todos requieren cookie `access_token` (en dev: `access_token=test`).

## 4. Tareas mínimas (checklist)
- [ ] Probar auth: `GET /api/transcriptions` (espera 200)
- [ ] Crear job async válido (YouTube): `POST /api/transcriptions`
- [ ] Polling de job: `GET /api/transcriptions/{id}` hasta `completed|failed|cancelled`
- [ ] Listar jobs y filtrar por estado
- [ ] Leer nodos y policy admin
- [ ] Cambiar capacidad de nodo y verificar efecto
- [ ] Cambiar perfil de nodo y verificar efecto
- [ ] Crear/actualizar perfil de modelo
- [ ] Leer cola y mostrar jobs activos
- [ ] Ejecutar rebalance manual
- [ ] Probar modo sync (video <= 300s, espera 200/422)
- [ ] Manejar errores comunes (401, 400, 422)

## 5. Ejemplo curl (crear job)
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

## 6. Referencia completa
Ver: `spec_dev/transcription_api_connectivity_guide.md` para detalles de payloads, respuestas y errores.
