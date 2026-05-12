# API Startup Evidence

Captured: 2026-05-12

## Command

```bash
cd services/api
PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8011
```

## Startup Result

```text
Started server process [22882]
Waiting for application startup.
Application startup complete.
Uvicorn running on http://127.0.0.1:8011 (Press CTRL+C to quit)
```

## Runtime Checks

```bash
curl -fsS http://127.0.0.1:8011/openapi.json -o docs/evidence/api/openapi-snapshot.json
curl -fsS http://127.0.0.1:8011/health
```

Health response:

```json
{"status":"ok","service":"retailops-api","environment":"local"}
```

Relevant access log lines:

```text
GET /openapi.json HTTP/1.1 200
GET /health HTTP/1.1 200
```

## Shutdown Result

```text
Shutting down
Waiting for application shutdown.
Application shutdown complete.
Finished server process [22882]
```

## Notes

The first sandboxed bind attempt failed with `operation not permitted`; the successful evidence run used the same Uvicorn command with permission to bind to local loopback.
