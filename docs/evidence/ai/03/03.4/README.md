# AI 03.4 — typed importer w repo AI

**Odbiór lokalny: 29.09.2026.** Implementacja znajduje się w
`retailops-ai-intelligence`, na nowym branchu **`ai/03-04-importer`**,
w osobnym worktree `/private/tmp/retailops-ai-03-04`.
Implementacja `aadd145e6f023078dcc34783247213d6fe8fdde5`, evidence `7d0f719`,
baza `4376cb8` (handoff + opublikowany RAG `abf3f69`).
Praca nad AI 12 pozostaje w niezależnym worktree; nie zmieniano jej plików.

Pełny runbook repo AI to `docs/source-snapshot-import.md`, karta danych
`docs/cards/source-snapshot-import.md`, a pomiary i fingerprints są w
`docs/evidence/03-04-importer.md`, `.json` i `docs/evidence/03-04/`.
[Handoff](../../../../reference/source-snapshot-handoff.md) utrzymuje tę samą
wersję 1.0.0/source 2.6.0; fixture i generator RetailOps pozostają bez zmian.

**706 testów passed**, w tym 48 nowych. Ruff/format, strict Mypy (110 plików),
istniejące kontrakty, docs/Required CI checker, wheel/sdist, Compose config
i Gitleaks przechodzą. Dwa istniejące testy real HTTP wymagały dostępu do
loopback poza sandboxem; pełny końcowy odbiór nie ma failures/errors/skips.

Importer ma osobne CLI `retailops-ai-snapshot` i extra `snapshot` z przypiętym
PyArrow. Sprawdza wszystkie manifesty/lineage, inventory, versions, paths,
byte SHA/size, typed Arrow schemas/nullability/metadata, counts, grain,
field/date ranges, date partitions i canonical multiset hashes.
Publikuje sealed staging przez fsync/no-replace rename pod source ID.
Identyczny reimport zachowuje bajty; konflikt, pusty lub uszkodzony destination
nie są nadpisywane. Source provenance i pełne observed-quantity versions
zostają zachowane. Source hard gates i wymagane use cases muszą kwalifikować input.

| Rzeczywiste wejście | Tabele / wiersze | Pliki | Import → reimport → verify, dwukrotnie | Max RSS |
|---|---:|---:|---:|---:|
| ai-smoke fixture | 25 / 31171 | 74 | 4,16–4,26 s | 76,83 MiB |
| ai-temporal-smoke, partition threshold 100 | 25 / 52973 | 1211 | 15,20–18,46 s | 62,47 MiB |
| ai-smoke z optional truth | 29 / 32759 | 83 | 5,47–7,26 s | 75,69 MiB |

Limity smoke: 300 s / 1024 MiB. Generacja/kwalifikacja źródła i curated nie są
w tym pomiarze konsumenta. Dodatkowe realne eksporty pochodzą z RetailOps
`b5d2804`, seed 42/end 2026-07-31; snapshoty zostały zapisane poza Git.
Temporal source/snapshot IDs oraz smoke facts IDs zachowują odbiór 03.2.

Testy obejmują forged byte SHA przy zmienionych rows, missing/extra/symlink/FIFO,
unsafe paths/version/identity/classification, source gate fail/not_ready,
concurrency, kontrolowaną awarię oraz SIGKILL/ukryty staging/retry.
Odłączony wheel przez `python -I` odbiera fixture bez obu checkoutów,
generatora, SQLAlchemy i API. Production no-replace publisher przeszedł
macOS oraz Linux aarch64 w pinned, readonly, offline kontenerze.

Truth jest default denied; opt-in zachowuje cztery osobne tabele i prywatne
modes, bez automatycznego joinu/runtime dostępu. Importer nie regeneruje
całej source qualification ani nie uwierzytelnia autora raportu.
Po SIGKILL może pozostać prywatny staging; owner musi sprawdzić aktywne procesy
przed cleanup. Pełny Linux/PyArrow flow czeka na Required CI.

Można rozpocząć **03.5 — curated**: mapping, normalizacja, kwarantanna,
availability/as-of i manifest transformacji. Następnie 03.6 cross-repo gate;
**04/06 pozostają zamknięte**. Nie wykonano treningu, nowych wywołań AWS,
push, zdalnego merge ani Required CI 03.4. Commity pozostają lokalne.
