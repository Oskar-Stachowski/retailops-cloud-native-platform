# Testowanie

[Dokumentacja](../README.md) · [Uruchomienie lokalne](local-development.md)

Polecenia poniżej uruchamiaj z katalogu głównego. Wspólnym interfejsem lokalnych
kontroli, GitHub Actions i Jenkinsa jest [Makefile](../../Makefile).

## Wybór kontroli

| Zmiana lub cel | Polecenie | Zakres |
|---|---|---|
| Backend i frontend | `make test` | Pytest API oraz testy usług frontendu w Node |
| Pełna lokalna kontrola kodu | `make ci-local` | Konfiguracja Compose, dane i kontrakty, Ruff, mypy, Bandit, coverage, frontend test/lint/build |
| Integracja z PostgreSQL | `make api-integration-test` | Migracje, ponowne załadowanie danych `demo`, testy z wymaganym połączeniem z bazą |
| Kontenery i monitoring | `make compose-ci` | Osobny stos Compose, testy HTTP/streamingu, Grafana/Prometheus oraz awaria API i powrót alertu do normy |
| Przeglądarka w osobnym stosie | `E2E_ALLOW_MUTATIONS=1 COMPOSE_BROWSER_TESTS=1 make compose-ci` | Powyższy zakres i scenariusze Chromium |
| Schematy i polityki Kubernetes | `make k8s-ci` | Renderowanie Kustomize, schematy, Conftest i Checkov |
| Działający Kubernetes | `make k8s-runtime-drill` | kind, ingress, polityki sieci, wolumeny, aktualizacja i rollback |
| Odtworzenie danych | `make db-recovery-drill` | Backup/restore i porównanie danych w osobnym środowisku |
| Wycofanie wersji aplikacji | `make release-drill` | Aktualizacja, wykrycie awarii i rollback zgodny z bieżącym schematem |

`make install` przygotowuje zależności Python i frontend. Kontrole Kubernetes,
IaC i bezpieczeństwa wymagają dodatkowych narzędzi opisanych w odpowiednich
instrukcjach; `make help` pokazuje wszystkie dostępne cele.

## Baza danych i zakres wyniku

Pytest obejmuje kontrakty API, domenę, repozytoria i usługi, dashboardy, workflow,
uprawnienia demo, migracje, seed oraz przetwarzanie zdarzeń. Nie jest ograniczony
do endpointu `/health`.

Testy oznaczone `integration_db` mogą zostać pominięte, gdy baza jest niedostępna.
Zmienna `REQUIRE_DB_TESTS=1` zamienia ten przypadek w błąd; używa jej CI i cel
`api-integration-test`. Sam zielony wynik lokalnego Pytest bez bazy nie potwierdza
integracji z PostgreSQL. Próg coverage w `pyproject.toml` wynosi 70%.

`api-integration-test` oraz testy workflow zmieniają wskazaną bazę. Uruchamiaj je
na danych przeznaczonych do testów. `compose-ci`, `db-recovery-drill`,
`release-drill` i `k8s-runtime-drill` mają własne izolowane środowiska i sprzątają
utworzone zasoby.

## Scenariusze przeglądarkowe

Specyfikacje w [frontend/e2e](../../frontend/e2e/) sprawdzają dashboard,
filtrowanie produktów i Product 360, zmianę stanu alertu, akceptację i zakończenie
rekomendacji, wymagany komentarz przy odrzuceniu, ograniczenia użytkownika
tylko do odczytu oraz ponowienie żądania po błędzie API.

Po instalacji zależności zainstaluj Chromium:

```bash
cd frontend
npx playwright install chromium
```

Następnie z katalogu głównego uruchom izolowany stos z testami przeglądarkowymi:

```bash
E2E_ALLOW_MUTATIONS=1 PLAYWRIGHT_BROWSER_CHANNEL= COMPOSE_BROWSER_TESTS=1 make compose-ci
```

Przebieg obejmuje także rzeczywistą dwuminutową awarię używaną do sprawdzenia
alertu. Raporty oraz logi z nieudanego przebiegu pozostają po automatycznym
usunięciu środowiska.

Przy pracy z już uruchomionym, przeznaczonym do testów stosem:

```bash
E2E_ALLOW_MUTATIONS=1 PLAYWRIGHT_BROWSER_CHANNEL= make browser-smoke
```

Bez pustego `PLAYWRIGHT_BROWSER_CHANNEL` cel Make domyślnie używa lokalnego
Google Chrome. Adresy można zmienić przez `FRONTEND_BASE_URL` i `API_BASE_URL`.
Scenariusze zmieniają stan workflow; kolejny przebieg może wymagać odtworzenia
danych.

## Pomiar wydajności

Na uruchomionym stosie i z zainstalowanym k6:

```bash
make performance-smoke
```

`K6_VUS` i `K6_DURATION` zmieniają obciążenie. `E2E_ALLOW_MUTATIONS=1 make runtime-smoke-evidence`
łączy testy HTTP, k6 i Playwright na tym samym istniejącym stosie. Ten mały test
zapisuje opóźnienia p95 i udział nieudanych żądań; nie wyznacza przepustowości
produkcyjnej.

## Gdzie szukać błędów

| Kontrola | Wynik |
|---|---|
| API coverage | `ci-cd/reports/api/coverage.xml` |
| Compose | `ci-cd/reports/docker/isolated-runtime.json`, `ci-cd/reports/docker-compose-logs.txt` |
| Awaria i odtworzenie monitoringu | `ci-cd/reports/observability/incident-drill.json` |
| Playwright | `ci-cd/reports/e2e/playwright-junit.xml`, ślady i zrzuty w `playwright-artifacts/` |
| k6 | `ci-cd/reports/performance/api-smoke.txt`, `api-smoke-summary.json` |
| Kubernetes | `ci-cd/reports/k8s-runtime/` |

Raport odnosi się do konkretnego przebiegu. Zmiana kodu lub zależności wymaga
ponownego uruchomienia odpowiedniej kontroli. Definicje zadań CI znajdują się
w [.github/workflows](../../.github/workflows/).
