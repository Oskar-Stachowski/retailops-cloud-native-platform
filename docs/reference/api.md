# API

[Dokumentacja](../README.md) · [Backend](../guides/backend.md) · [Kontrakt list](api-list-contract.md)

FastAPI udostępnia dane operacyjne, agregaty dashboardu, akcje workflow oraz
metadane przebiegów prognozowania. Przy domyślnej konfiguracji dokumentacja
interaktywna działa pod <http://localhost:8000/docs>, a bieżący schemat pod
<http://localhost:8000/openapi.json>. Frontend korzysta z tych samych tras przez
proxy `/api`.

## Dostępne obszary

| Obszar | Endpointy |
|---|---|
| Stan i metryki | `GET /health`, `GET /ready`, `GET /metrics` |
| Produkty | `GET /products`, `GET /products/{product_id}`, `GET /products/{product_id}/360` |
| Sprzedaż i zapas | `GET /sales`, `GET /sales/{sale_id}`, `GET /inventory-snapshots`, `GET /inventory-snapshots/{inventory_snapshot_id}`, `GET /inventory-risks` |
| Prognozy | `GET /forecasts`, `GET /forecasts/{forecast_id}` |
| Przebiegi modeli | `GET /forecast-runs`, `GET /forecast-runs/{forecast_run_id}`, `POST /forecast-runs` |
| Dashboard | `GET /dashboard/summary`, `/dashboard/operational-visibility`, `/dashboard/sales-trend`, `/dashboard/alerts`, `/dashboard/recommendations`, `/dashboard/open-work-items`, `/dashboard/stock-risk-summary`, `/dashboard/live-operations` |
| Analityka | `GET /analytics/products`, `GET /analytics/inventory-risk` |
| Tożsamość demo | `GET /users/demo`, `GET /me`, `GET /me/permissions` |
| Powiadomienia demo | `GET /notifications`, `POST /notifications/{notification_id}/read` |

Zmiany workflow używają osobnych endpointów `POST`:

- `/alerts/{alert_id}/acknowledge`, `/assign`, `/resolve`, `/dismiss`, `/comment`;
- `/recommendations/{recommendation_id}/accept`, `/reject`, `/assign`, `/resolve`, `/dismiss`.

Skrócone końcówki oznaczają ten sam prefiks i identyfikator zasobu. Nie ma
samodzielnych list `GET /alerts` ani `GET /recommendations`; odczyty zapewniają
dashboard i Product 360. Publiczne API nie wystawia `reopen` ani `escalate`.

## Kontrakty odpowiedzi

Trwałe kolekcje biznesowe korzystają z `items` oraz
`pagination: {limit, offset, total}`. Filtry, dozwolone sortowanie i maksymalny
`limit` zależą od endpointu. Dashboardy i analityka mają kontrakty agregatów;
nie należy zakładać jednakowej struktury wszystkich odpowiedzi.

```bash
curl 'http://localhost:8000/products?limit=10&offset=0&sort_by=sku&sort_order=asc'
curl 'http://localhost:8000/dashboard/live-operations?window_minutes=15'
curl 'http://localhost:8000/me?user_id=ops-manager'
```

`POST /forecast-runs` zapisuje metadane modelu, zbioru cech, metryk i ścieżek
artefaktów. Operacja wykonuje upsert po `run_key` i zwraca HTTP 201. Nie trenuje
modelu, nie importuje prognoz do tabeli `forecasts` i nie publikuje modelu.

Obsługiwane błędy HTTP i walidacji mają postać:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": []
  }
}
```

`details` jest opcjonalne. Typowe wyniki to 403 dla braku uprawnień demo, 404 dla
nieznanego zasobu, 409 dla niedozwolonego przejścia workflow i 422 dla błędnego
żądania. `/ready` zwraca 503, gdy sprawdzenie połączenia z bazą nie powiedzie się.

## Workflow i tożsamość

Żądanie workflow może zawierać `comment`, `assigned_to_user_id` i
`idempotency_key`. Klucz idempotencji jest polem JSON, a nie nagłówkiem HTTP.
Przypisanie wymaga UUID użytkownika z tabeli `users`. Komentarz, jeśli podany,
ma 5–1000 znaków; odrzucenie i pominięcie wymagają uzasadnienia. Dozwolone stany
i znaczenie operacji opisują [procesy biznesowe](business-workflows.md).

Parametr `user_id` wybiera użytkownika demonstracyjnego, np. `ops-manager`.
Pominięcie go wybiera `platform-admin`. Wybrane mutacje sprawdzają uprawnienia,
ale ten mechanizm nie uwierzytelnia klienta. Powiadomienia i stan ich odczytania
są przechowywane w pamięci procesu. Szczegóły:
[granica tożsamości demo](../security/demo-auth-boundary.md).

## Diagnostyka i źródła kontraktu

`/health` potwierdza działanie procesu, a `/ready` wykonuje `SELECT 1` w bazie.
Żaden z tych wyników nie potwierdza kompletności migracji ani danych. Nagłówek
`X-Correlation-ID` wiąże żądanie z logami; API generuje go, jeśli klient go nie
prześle lub przekaże nieprawidłową wartość.

Definicje utrzymuj razem z implementacją:

- [rejestracja routerów](../../services/api/app/main.py);
- [routery i parametry](../../services/api/app/api/);
- [schematy Pydantic API](../../services/api/app/api/schemas.py);
- [obsługa błędów](../../services/api/app/api/errors.py);
- [testy kontraktów](../../services/api/tests/).
