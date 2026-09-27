# Fundament AI 01 — pakiet i serwis HTTP

Data: **2026-09-27**. Aktualny zakres to lokalny pakiet i diagnostyka HTTP;
cały etap 01 pozostaje `in_progress`. Źródło planu tego zakresu w RetailOps:
`c89da89`, baza repo AI: `5da5fdc`.

## Repo i wersje

Repo lokalne: `/Users/oskarstachowski/retailops-ai-intelligence`,
obok RetailOps, branch `ai/implementation`. Brak remote i publikacji na GitHub.

| Commit w repo AI | Zakres |
|---|---|
| `e6c78886be9ef151417ee7e5fc91cc817e1bec40` | Bazowy HTTP, warstwy api/domain/pipelines/adapters, kontrole zależności, bezpieczne błędy, logi, trace i metryki; kontrakty i 62 testy. |
| `7d67530ca574e4acf60405c22fdde1ec59f1f174` | Dowody czystego checkoutu, blokady błędnego kontraktu i działania HTTP z zainstalowanej paczki wheel. |

Pełne komendy, wyniki i sumy kodu/artefaktów są w repo AI:
`docs/evidence/01-http.md` oraz `docs/evidence/01-http.json`.
Bieżące uruchomienie i ograniczenia opisują `docs/http-service.md`,
`docs/development.md` oraz `docs/STATUS.md`. Ten wpis wskazuje dowody
między repozytoriami; nie tworzy drugiej instrukcji obsługi.

## Weryfikacja

- macOS ARM64, Python **3.11.15**, uv **0.12.19**, przypięte zależności.
- Czysty checkout `e6c7888` i nowe venv z lockfile oraz lokalnego cache:
  `make ci-local` — **62 passed in 2.82s**, bez pominięć, Ruff/format, Mypy strict
  (18 plików), kontrakty, dokumentacja, build i skany sekretów.
- Wymagana awaria/timeout → readiness 503; opcjonalna → 200 degraded.
  Health nie sonduje providerów. Są to próby na fakes, nie na rzeczywistej DB.
- Testy sprawdzają izolację równoczesnych żądań, W3C parent/child i przekazanie
  kontekstu, chronione metryki, ograniczone etykiety i brak wartości wejściowych
  w błędach/logach. Wyłączony SDK tracingu nie wyłącza HTTP.
- Rzeczywisty proces na loopback obsłużył cztery endpointy i zakończył lifespan.
  Próba została powtórzona z wheel w osobnym środowisku runtime, poza checkoutem;
  import pochodził z site-packages, a `uv pip check` potwierdziło zależności.
- Po przeniesieniu commitów do docelowego repo odtworzono venv z lockfile:
  test rzeczywistego procesu i test dotenv przeszły (2 passed in 0.94s),
  config-check i linki były poprawne, branch i worktree pozostały czyste.
- Celowo błędny schemat health dał exit 1 testu kontraktu. Plik przywrócono,
  checkout pozostał czysty. Actionlint potwierdził workflow.

Readiness roli foundation oznacza obecnie zakończony startup, bez deklaracji
gotowości bazy/modelu. Lokalny bind i token metryk nie są auth przyszłego API AI.
Nie wykonano zdalnego CI, ochrony gałęzi, DB/MLflow, trwałego restartu, modeli,
eksportu OTLP ani AWS. Następny zakres: [persistence i Compose](../../../plans/ai/backlog.md).
