# Diagnostyka lokalnego Compose

Punkt startowy: [uruchomienie lokalne](../guides/local-development.md).
Poniższe polecenia dotyczą własnego środowiska deweloperskiego. Zachowaj jego
`COMPOSE_PROJECT_NAME`, profile i porty z `.env`.

## Sprawdź usługi i zależności

```bash
docker compose --profile dev --profile observability ps -a
docker compose --profile dev --profile observability logs --tail=100 db migrate seed api frontend
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/ready
curl --fail http://localhost:3000/api/health
```

| Objaw | Co sprawdzić |
|---|---|
| Zajęty port | Sprawdź proces zajmujący dany port; ustaw wolny `API_PORT`, `FRONTEND_PORT`, `POSTGRES_PORT`, `PROMETHEUS_PORT` lub `GRAFANA_PORT` w `.env`. |
| API nie jest gotowe | Logi bazy, migracji i seeda; dane połączenia muszą odpowiadać uruchomionej bazie. |
| Seed kończy się błędem | Wybrany profil i pliki CSV. Na pierwsze demo wybierz `RETAILOPS_SEED_DATA_PROFILE=demo`; patrz [baza](../guides/database.md). |
| Frontend nie widzi API | Sprawdź `/api/health` przez Nginx oraz proxy `/api` w Vite. Używaj `VITE_API_BASE_URL=/api`. |
| `/` API zwraca 404 | To nie jest endpoint zdrowia. Użyj `/health`, `/ready` lub `/docs`. |
| Live Operations jest puste | Sam broker nie tworzy zdarzeń. Sprawdź [konsumenta i ruch demonstracyjny](../guides/streaming.md). |
| Brak metryk lub dashboardów | [Runbook monitoringu](observability-runbook.md). |

Nie usuwaj wolumenów jako pierwszego kroku diagnostyki. `make compose-down`
wykonuje `down -v` i usuwa dane. Do zwykłego zatrzymania służy:

```bash
docker compose --profile dev --profile observability stop
```

Ponowne wykonanie zadania seed nadpisuje tabele demonstracyjne; restartuj
samą usługę, jeżeli nie zamierzasz odtwarzać danych.

## Nieudana próba CI

`make compose-ci` uruchamia odrębny projekt i usuwa jego zasoby po zakończeniu.
Sprawdź `ci-cd/reports/docker-compose-logs.txt`,
`ci-cd/reports/docker/isolated-runtime.json` oraz
`ci-cd/reports/observability/incident-drill.json`.
Polecenie `docker compose logs` bez nazwy tego projektu nie odtworzy jego logów.
Warunki powtórzenia próby: [testowanie](../guides/testing.md).
