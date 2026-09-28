# Fundament AI 01 — HTTP i persistence

Aktualizacja: **2026-09-28**. Działa pakiet, diagnostyka HTTP i lokalny
stos PostgreSQL/pgvector/MLflow z jawnymi migracjami. Cały etap 01 pozostaje
`in_progress`. [Raport persistence](persistence.json) dotyczy implementacji
`7e0978b`; wcześniejszy HTTP miał bazę `5da5fdc` i plan RetailOps `c89da89`.

## Repo i wersje

Repo lokalne: `/Users/oskarstachowski/retailops-ai-intelligence`,
obok RetailOps, branch `ai/implementation`; origin na GitHub. Nowe commity
tego zakresu pozostają lokalne.

| Commit w repo AI | Zakres |
|---|---|
| `e6c78886be9ef151417ee7e5fc91cc817e1bec40` | Bazowy HTTP, warstwy api/domain/pipelines/adapters, kontrole zależności, bezpieczne błędy, logi, trace i metryki; kontrakty i 62 testy. |
| `7d67530ca574e4acf60405c22fdde1ec59f1f174` | Dowody czystego checkoutu, blokady błędnego kontraktu i działania HTTP z zainstalowanej paczki wheel. |
| `7e0978b7a3d14ba222c7c305d8b995e960369fc1` | PostgreSQL/pgvector AI, oddzielny MLflow, migracje, Compose, rzeczywista sonda DB oraz 77 testów. |
| `7bd17e65a3bb5416620526a8b48e14986923d140` | Dowody czystego checkoutu i nowych wolumenów oraz odczyt bieżącego stanu GitHub. |

Pełne komendy, wyniki i sumy kodu/artefaktów są w repo AI:
`docs/evidence/01-http.md/json` i `docs/evidence/01-persistence.md/json`.
Bieżące uruchomienie i ograniczenia opisują `docs/http-service.md`,
`docs/local-stack.md`, `docs/development.md` oraz `docs/STATUS.md`. Ten wpis wskazuje dowody
między repozytoriami; nie tworzy drugiej instrukcji obsługi.

## Persistence — rzeczywisty lokalny runtime

Czysty checkout `7e0978b`, nowe venv i nowe wolumeny:
`make bootstrap ci-local` — exit 0, **77 passed in 8.80s**, bez pominięć;
lint/format, Mypy strict (25 plików), kontrakty/docs, wheel/sdist, Compose config
oraz skany sekretów przechodzą. `scripts/verify_local_stack.py` — exit 0:

- Oddzielne bazy i nieuprzywilejowane role AI/MLflow, odrzucone oba połączenia
  do bazy drugiej aplikacji; vector 0.8.6 tylko w bazie AI.
- Jawne migracje i ponowienie; nieaktualna wersja schematu blokuje readiness,
  a restart API nie migruje bazy automatycznie.
- Metadane AI i artefakt MLflow przetrwały SIGKILL i restart. Down/up zachowało
  rekord AI, eksperyment MLflow i identyczną treść pliku.
- Po zatrzymaniu DB: health 200, readiness 503 z ai_db down/timeout.
  Po jej powrocie readiness 200 bez restartu API.
- Porty hosta są loopback, DB bez publikacji, backend internal; osobny frontend
  API/MLflow potrzebny do publikacji portów na Docker Desktop. Brak blokady
  egress tych usług, brak aplikacyjnego auth MLflow. Logi końcowego uruchomienia
  nie zawierały wygenerowanych haseł/tokenu. Shutdown zachował wolumeny.

API w obrazie działa z wheel, bez source mount. Sonda ai_api sprawdza wersję
Alembic, rozszerzenie vector i tabelę. Nie potwierdza modeli ani predykcji.
Raport odróżnia fake testy adaptera od rzeczywistych usług.
Po fast-forward commitów do docelowego repo odtworzono venv z lockfile; testy
procesu HTTP i rzeczywistego niedostępnego DB przeszły (2 passed in 5.63s),
a worktree pozostał czysty.

Odczyt GitHub 28.09.2026: main chronione z wymaganym required-result,
[Required CI bazowego 7d67530 ma success](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/actions/runs/36383297184).
Zdalnego CI nowej implementacji nie wykonano, bo nowe commity nie zostały wypchnięte.
Cały etap 01 pozostaje otwarty: [kontrakty i uprawnienia](../../../plans/ai/backlog.md).
Nie odebrano Linux x86_64 runtime, backup/restore, modeli, RAG, OTLP ani AWS.

## HTTP — wcześniejszy pomiar 27.09.2026

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

W pomiarze HTTP readiness roli foundation oznaczało zakończony startup, bez deklaracji
gotowości bazy/modelu. Lokalny bind i token metryk nie są auth przyszłego API AI.
Pomiar HTTP nie obejmował DB/MLflow ani trwałego restartu; aktualny odbiór
tych usług jest opisany wyżej. Token metryk pozostaje lokalną ochroną telemetrii.
