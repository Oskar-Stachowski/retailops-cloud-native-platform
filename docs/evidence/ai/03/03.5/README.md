# AI 03.5 — curated w repo AI

**Odbiór lokalny: 29.09.2026.** Repo `retailops-ai-intelligence`, branch
`ai/03-04-importer`, osobny worktree `/private/tmp/retailops-ai-03-04`.
Implementacja `4e4717b9304a8668103aa4c0f5d65de46a57453a`, blokada niejednoznacznych
planów `073b22e38953472e622f6f2c44a95963f7717136`; evidence `ab03a1fea0669dd437f9147815aad8e46e9c0237`. AI 12 pozostał niezależny.

Pełny runbook w repo AI: `docs/curated.md`; karta `docs/cards/curated.md`;
evidence `docs/evidence/03-05-curated.md`, `.json` oraz `docs/evidence/03-05/`.
[Handoff](../../../../reference/source-snapshot-handoff.md) pozostaje 1.0.0/source 2.6.0.
Generator i źródłowy fixture nie były zmieniane.

**743 testy passed**, w tym 37 nowych, bez failures/errors/skips.
Ruff/format, strict Mypy (117), istniejące kontrakty, docs/Required CI contract,
wheel/sdist, Compose config i staged Gitleaks przechodzą. Pełna regresja użyła
loopback poza sandboxem, bez pomijania istniejących testów HTTP.

Curated normalizuje typed facts/plans, NFC/UTC, jawne dictionary/unit/currency
policies i uzgadnia product/selling/channel/stock przez source katalogi,
assignment/route/assortment. Nie tworzy zastępczych lokalizacji ani zer.
Odrzucone rekordy zachowują row/grain/hash/reason w prywatnej kwarantannie;
dowolny rejection blokuje ready publication i trafia tylko do curated-rejected.

Curated ID ma parents, config/watermarks, exact code/schema/lock fingerprints,
Python/PyArrow i typed content/counts/grain/ranges/rejections. Publikacja jest
fsync/no-replace; re-build zachowuje bajty, inny układ plików zachowuje logiczny ID.
Historia zachowuje wszystkie quantity versions; as-of wybiera wersję znaną
w origin, bez final quantity z latest table i bez przyszłych business dates.
Przyszły plan jest dozwolony tylko w znanej wersji; konkurencyjne najwyższe
wersje blokują odczyt.

| Przypięte wejście | Curated tabele / wiersze | Consumer przebieg, dwukrotnie | Max RSS |
|---|---:|---:|---:|
| fixture | 25 / 31171 | 49.59–66.75 s | 104.22 MiB |
| temporal | 25 / 52973 | 122.14–134.65 s | 100.53 MiB |
| truth | 25 / 31171 | 65.03–70.83 s | 106.08 MiB |

Pomiar obejmuje import → build → rebuild → verify → dwa as-of z niezależnym
porównaniem raw source versions; limit 300 s / 1024 MiB per fresh worker.
Wszystkie tabele/wersje zachowano, quarantine = 0. Truth input ma 29 tabel,
ale curated nadal tylko 25 facts/plans, bez truth access/joinu.
Inputs pochodzą z 03.3/03.4: fixture `6561481`, realne temporal/truth `b5d2804`,
seed 42/end 2026-07-31. Nie wykonano nowej generacji/qualification upstream.
Inne lokalne kontrole mogły pracować równolegle; RSS dotyczy każdego procesu.

Odłączony wheel przez `python -I` odtworzył import/build/rebuild/verify/as-of
bez generatora, API i SQLAlchemy, z identycznym curated ID i fingerprints
jak fresh fixture acceptance. Aktualny fixture curated zachowano poza Git
w worktree AI, `data/generated/curated/curated-sha256-6d7c6088199cd0505ad5a91ff0fbca171960e900e4a00f2e3dfb55a0617cade3/`.

Testy obejmują brak/niedostępność/niejednoznaczność mappingu, data-gap vs zero/
closed, mikrosekundowy cutoff, late correction, version gap/regression,
conflicting plans, forged byte SHA, path/schema/version faults, concurrency,
handled failure, SIGKILL/hidden private staging/retry, truth i write budget.

Statyczne/legacy atrybuty bez source availability pozostają not_recorded.
Curated nie tworzy features/labels/modeli. Inventory false; ML/replay not_ready.
Truth pozostaje w osobnym parent import; ten sam UID nie jest izolowany modes.
Po SIGKILL owner sprawdza aktywne procesy przed cleanup. Pełny Linux oraz
ai-dev/ai-training pozostają poza tym odbiorem.

**Można rozpocząć 03.6 — pełną bramkę cross-repo**, z przypiętymi rewizjami
obu repo i pomiarem generator → qualification → export → import → curated.
04/06 pozostają zamknięte. Nie wykonano push, remote merge, Required CI 03.5,
treningu ani nowych wywołań AWS. Commity pozostają lokalne.
