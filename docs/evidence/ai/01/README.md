# Fundament AI 01 — lokalne auth, kontrakty i persistence

Aktualizacja: **2026-09-28**. Działa pakiet, HTTP, lokalny stos
PostgreSQL/pgvector/MLflow, kontrakty danych/run/tool i lokalne poświadczenia/scope API.
[Raport auth](access.json) dotyczy implementacji `01eca67` i dowodów `2f067c6`.
[Raport kontraktów](contracts.json) dotyczy implementacji `ae21d4e` i dowodów
`40ad85c`; osobny [raport persistence](persistence.json) implementacji `7e0978b`.
Cały etap 01 pozostaje `in_progress`.

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
| `ae21d4e37dc56fb6d12c53f103190aa663b9a0f0` | Kontrakty v1 dataset/feature/label/split/model/prediction/run/tool/bundle, schemas, fixtures, semantyczny CLI i wymagana bramka CI; 208 testów. |
| `40ad85c39551f00546b994e902e476f0b171ac07` | Odbiór czystego checkoutu, paczki wheel poza źródłami oraz blokady celowo błędnego schema. |
| `01eca67b1af4d0e082770ddb3e26dee601fa9d02` | Prywatne poświadczenia, immutable principal i whole-scope/capabilities; chronione identity, preflight i admin metadata, schemas oraz 267 testów. |
| `2f067c68cb5931ef31578f724e496f5381b3ae6a` | Dowody czystego checkoutu i rzeczywistego auth HTTP z wheel, z restartem po revoke. |

Pełne komendy, wyniki i sumy kodu/artefaktów są w repo AI:
`docs/evidence/01-http.md/json`, `01-persistence.md/json`, `01-contracts.md/json` i `01-access.md/json`.
Bieżące uruchomienie i ograniczenia opisują `docs/http-service.md`,
`docs/local-stack.md`, `docs/data-contracts.md`, `docs/access-control.md`,
`docs/development.md` i `docs/STATUS.md`. Ten wpis wskazuje dowody
między repozytoriami; nie tworzy drugiej instrukcji obsługi.

## Lokalna tożsamość i uprawnienia — odbiór 28.09.2026

Czysty checkout `01eca67`, nowy venv: `make bootstrap ci-local` — exit 0,
**267 passed in 12.27s**, bez pominięć. Ruff/format, Mypy strict (48 plików),
docs/contracts/snapshots, wheel/sdist, Compose config i skany sekretów przechodzą.
Actionlint przechodzi. Runtime dependencies i lockfile pozostają zgodne;
diagnostyczny OpenAPI oraz intelligence fixtures nie zmieniły się.

- Prywatna mapa poza Git: server grants/capabilities, fingerprints losowych
  tokenów oraz not-before/expiry/revoked. Loader odrzuca symlink/FIFO/inne UID,
  otwarte permissions, niepoprawny/za duży/niejednoznaczny JSON i błędne references.
- Identity, forecast scope preflight i admin policy metadata wymagają credentials.
  401 dla braku lub błędu; 403 dla braku capability lub choć jednej obcej jednostki.
  Role nie są hierarchiczne, admin bez jawnego forecast:read nie uzyskuje odczytu.
- Body/query/header role/user_id, cookie lub duplicate Authorization nie nadają
  tożsamości. Token metryk jest osobny, reuse odrzucany. Request ma limity i
  bezpieczne błędy; logi/metryki nie zawierają tokenów, fingerprintów lub danych body.
- Schemas/OpenAPI mają pozytywne/negatywne testy i wymaganą bramkę; celowo usunięte
  security ze snapshotu daje exit 1. access-init nie drukuje tokenów i nie nadpisuje
  istniejących plików: katalog 0700, policy/client credentials 0600.

Wheel zainstalowano poza checkoutem w osobnym venv z produkcyjnymi zależnościami
z lockfile i hash verification; `uv pip check` przechodzi, import z site-packages,
bez jsonschema dev. Rzeczywisty HTTP: identity 401/200, scope 200 i trzy 403,
admin 403/200, admin→forecast 403, podszyty principal 422; health/readiness 200.
Po zmianie revoked na dysku działający proces zachował snapshot. Restart odrzucił
token 401. Oba procesy zakończyły lifespan, bez sekretów/private path w logach,
bez katalogu artefaktów. Po fast-forward docelowego repo: locked bootstrap,
**60 testów auth/rzeczywistych procesów in 3.19s** i snapshots przechodzą;
worktree pozostaje czysty.

Forecast-check to autoryzacja zakresu, bez odczytu prognozy lub walidacji source IDs.
Polityka jest lokalnym startup snapshotem: grants/revoke/rotation wymagają restartu,
expiry działa per request. Nie ma OIDC/JWT/publicznego IAM/tenant/audit store,
rate limiter, rzeczywistego tool executora lub serving. Obecny Compose nie montuje
policy, więc /api/v1 pozostaje zamknięte; MLflow nie ma aplikacyjnego auth.
Nie ponawiano pełnego DB/crash/restart smoke; wcześniejszy pomiar niżej pozostaje
osobny. Lokalny zakres 01 ma odbiór; zdalny Required CI nowych commitów czeka na push.

## Kontrakty — osobny odbiór 28.09.2026

Czysty checkout `ae21d4e`, nowy venv: `make bootstrap ci-local` — exit 0,
**208 passed in 9.56s**, bez pominięć. Ruff/format, Mypy strict (40 plików),
linki/CI, snapshots, wheel/sdist, Compose config i skany Gitleaks przechodzą.
Actionlint przechodzi; poprawiono wyrażenie wyniku persistence w required-result
oraz dodano guard workflow. Diagnostyczne HTTP/OpenAPI fixtures pozostają zgodne.

- 10 rodzin schema Draft 2020-12, dokładna wersja 1.0, brak unknown fields/coercji.
  Pozytywne przykłady są sprawdzane przez niezależny jsonschema oraz Pydantic.
  55 ręcznych negatywnych fixtures rozróżnia odrzucenie struktury i semantyki.
- Full forecast grain, UTC/end-of-day/horizon, granica mikrosekundy availability,
  znane plany vs przyszłe facts, jawne null/missing/censored vs obserwowane zero.
- Oddzielne content IDs każdej roli oraz byte checksums, requested/resolved config,
  provenance i source ownership. Truth/raw/operational outputs nie są feature input.
- Zamknięty graf source → curated → features/labels → split → training/model →
  inference/prediction: rodzice, logical content, rows, daty i complete output.
  Kontrola maturity, training label availability i selection przed testem.
- Legalne przejścia runa, przypięte wejścia, brak partial output i przepisywania
  terminalnych wyników; bounded read tool z no_data/error, scope i freshness.
- Offline CLI odrzuca duplicate JSON keys/nonfinite/za duży dokument,
  nie pokazuje wejścia w błędzie i nie wymaga konfiguracji usług.
  Celowe osłabienie schema daje niezerowy exit bramki, bez auto-poprawy w CI.

Wheel działa w osobnym venv, poza checkoutem, z hash-verified produkcyjnymi
zależnościami z uv.lock; `uv pip check` przechodzi, import z site-packages,
bez dev jsonschema. Valid bundle → exit 0, late feature → exit 2,
prywatne wejście → stały błąd bez wartości; brak katalogu artefaktów.
Po fast-forward do docelowego repo: locked bootstrap, **137 testów kontraktów/CI
in 2.14s** i bundle CLI przechodzą. Branch ai/implementation i worktree są czyste.

Przykłady to syntetyczne metadane: checksums/model/run i passed flags ilustrują
format, nie odpowiadają fizycznym plikom ani treningowi. Walidacja nie weryfikuje
byte checksums, source gates lub rzeczywistego użycia splitu. Run nie jest workerem,
tool nie ma executora/auth/agenta. Import/ML/streaming wymagają późniejszych etapów.
Nie ponawiano Compose crash/restart dla tej zmiany kontraktów; osobny pomiar niżej
zachowuje datę i zakres. Nowe commity nie zostały wypchnięte — zdalny CI pozostaje otwarty.

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
Cały etap 01 pozostaje otwarty: [odbiór zdalnego CI nowych commitów](../../../plans/ai/backlog.md).
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
