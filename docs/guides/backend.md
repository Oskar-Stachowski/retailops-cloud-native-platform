# Backend

[Dokumentacja](../README.md) · [API](../reference/api.md) · [Baza danych](database.md) · [Testowanie](testing.md)

Backend w `services/api/` to FastAPI na Python 3.11. Udostępnia dane sprzedaży
i zapasu, prognozy, dashboardy, Product 360, mutacje workflow, użytkowników demo,
odczyt Live Operations i metadane przebiegów modeli.

## Uruchomienie

Pełny stos i konfigurację `.env` opisuje [instrukcja lokalna](local-development.md).
Compose przygotowuje bazę, migracje i seed przed uruchomieniem API.

Do pracy z automatycznym przeładowywaniem kodu zainstaluj zależności przez
`make api-install`, przygotuj bazę według [przewodnika PostgreSQL](database.md)
i uruchom w katalogu `services/api/`:

```bash
DATABASE_URL=postgresql://retailops:retailops@localhost:5432/retailops \
  .venv/bin/uvicorn app.main:app --reload
```

Adres powyżej odpowiada niezmienionym danym logowania z `.env.example`.
Uwzględnij własne ustawienia i zatrzymaj kontener API, jeśli zajmuje już port
8000. Uvicorn uruchomiony bez Make nie wczytuje automatycznie głównej `.env`.

## Podział kodu

| Ścieżka w `services/api/` | Odpowiedzialność |
|---|---|
| `app/main.py` | Składanie aplikacji, routerów i middleware |
| `app/api/` | Endpointy, publiczne schematy i kontrolowane błędy |
| `app/domain/` | Modele Pydantic i reguły przejść workflow |
| `app/services/` | Logika operacyjna, agregaty i przetwarzanie zdarzeń |
| `app/repositories/` | Zapytania i transakcje Psycopg |
| `app/db/` | Połączenia PostgreSQL i instrumentacja zapytań |
| `app/auth/` | Użytkownicy i uprawnienia demonstracyjne |
| `app/core/` | Konfiguracja, logowanie, korelacja i opcjonalne śledzenie żądań |
| `alembic/versions/` | Wersjonowane migracje z SQLAlchemy Core |
| `scripts/`, `tests/` | Polecenia operacyjne i testy |

## Konfiguracja i diagnostyka

[config.py](../../services/api/app/core/config.py) odczytuje konfigurację ze
zmiennych środowiska. Najważniejsze to `APP_ENV`, `DATABASE_URL`, `CORS_ORIGINS`
oraz `RETAILOPS_BROKER_BOOTSTRAP_SERVERS`. Konfiguracja OpenTelemetry jest
opisana w [instrukcji tracingu](../observability/api-tracing.md).

| Endpoint | Co potwierdza |
|---|---|
| `/health` | Proces API odpowiada |
| `/ready` | API wykonuje `SELECT 1` w PostgreSQL |
| `/metrics` | Ekspozycja metryk dla Prometheusa |
| `/docs`, `/openapi.json` | Aktualny kontrakt uruchomionej aplikacji |

Middleware dodaje `X-Correlation-ID` do odpowiedzi i loguje czas oraz wynik
żądania. `/ready` nie weryfikuje aktualności migracji ani kompletności danych.

## Zdarzenia i zapisy

Procesor niezależny od brokera zapisuje wyniki przetwarzania w tabelach
strumieniowych. Proces `scripts/run_realtime_consumer.py` obsługuje ciągły odczyt
Redpandy/Kafki; uruchamia go `make realtime-consumer` lub workload lokalnego
Kubernetes. Sam start Uvicorn nie uruchamia pętli odczytu brokera. Instrukcja:
[streaming](streaming.md).

Mutacje alertów i rekomendacji są trwałe, podobnie jak zapis przez
`POST /forecast-runs`. Tożsamość demo oraz stan przeczytania powiadomień pozostają
w pamięci. Uprawnienia demo nie zastępują uwierzytelnienia produkcyjnego.

## Kontrola zmian

Z katalogu głównego:

```bash
make api-test
make api-lint
make api-format-check
make api-type-check
```

Testy bazodanowe mogą być pominięte bez działającego PostgreSQL. Pełną integrację,
coverage i izolowane testy kontenerów opisuje [przewodnik testowania](testing.md).
Zestaw zależności runtime jest w `services/api/requirements.txt`, a narzędzia
deweloperskie w `services/api/requirements-dev.txt`.
