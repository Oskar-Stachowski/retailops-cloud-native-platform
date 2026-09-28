# AI 03.2 — niezmienny exporter

**Odbiór lokalny: 28.09.2026.** RetailOps, branch `ai/03-01-parquet`,
implementacja `6561481506d9e5ec9f7fc48bbe54a80567420128`, baza `d721125`.
[Runbook](../../../../reference/ai-snapshots.md) podaje istniejący CLI,
allowlistę i granice odbioru. [Rejestr weryfikacji](verification.json)
zawiera polecenia, wyniki, provenance i ograniczenia.

## Wyniki

**155 testów passed:** 71 formatu/polityki/snapshotów i 84 zgodności source
identity, generatora oraz append-only historii/as-of. Regresje zgodności użyły
rzeczywistego izolowanego Docker workera. Ruff check/format, Bandit high/high,
Gitleaks staged i diff check przeszły.

[Benchmark](benchmark.json) wykonał generator → kwalifikację pełnego źródła →
eksport → odczyt/checksums/parity → niezmienny re-export. Oba profile uruchomiono
dwukrotnie w świeżych procesach. Seed 42, end date 2026-07-31, chunk 8192,
Python 3.11.15, PyArrow 25.0.1, macOS arm64. Pomiary wykonano na bazie `d721125`
z implementacją w worktree; zapisane code-file hashes odpowiadają commitowi
`6561481`. Osobne uruchomienia obu CLI na tym commicie potwierdziły te same IDs.

| Profil | Wiersze 25 eksportowanych tabel | Pełny przebieg | Max peak RSS | CSV całego źródła | Eksport Parquet |
|---|---:|---:|---:|---:|---:|
| ai-smoke | 31171 | 36,81–38,27 s | 120,50 MiB | 9289735 B | 1396368 B |
| ai-temporal-smoke | 52973 | 65,20–69,55 s | 156,17 MiB | 15662801 B | 2289699 B |

`ai03-snapshot-budget-1.0.0` wymusza **300 s / 1024 MiB na pełny profil**.
Instalacja zależności pozostaje poza pomiarem. Równolegle działały inne lokalne
testy; nie jest to porównanie sprzętu ani pomiar pełnego Linux CI.

| Profil | Source ID | Snapshot ID |
|---|---|---|
| smoke | `source-sha256-a12866e1099c3ae2ae7c73cac5c533a35733618d85a3728cd5f0e1c7b527fc00` | `snapshot-sha256-4d856185ebbe3a8f07dc468468c54eacf69aa40b7d49bfff7e39af8ddde815a4` |
| temporal | `source-sha256-94829460645140b79a6f68e87194f74d2c8e55392e2702a9fecbe6b771116d22` | `snapshot-sha256-d84c7b9630c6a34f7807abc7560253bf8e7ba3d7d962abee8aca580cf909b767` |

[Manifest smoke](manifest-smoke.json) i [manifest temporal](manifest-temporal.json)
są pełnymi manifestami publikacji na `6561481`. Zawierają source repo/commit,
generator/calendar/contract versions, seed, requested/effective config,
watermarks/readiness, schema, grain, klasy, counts/date ranges, physical
bytes/checksums i canonical content hashes. Dane CSV/Parquet pozostają poza Git.

## Kontrole publikacji

Pełne źródło jest najpierw kopiowane i sprawdzane w prywatnym stagingu.
Eksporter przelicza kontrakty, 46 hard gates i realism na tej kopii.
Test z ujemną kwotą zamówienia, poprawionymi checksums/logical identity i nadal
`passed` w starym raporcie jest odrzucany. Zmiana oryginalnego CSV po kwalifikacji
nie wpływa na zapisane dane. Forecast-source jest gotowy; modele, anomaly,
stockout i replay pozostają `not_ready`, rag `not_applicable`, inventory false.
Wymaganie niegotowego zastosowania blokuje eksport.

Publikacja następuje po pełnej weryfikacji, fsync i atomowym rename bez
nadpisania destination. [Próba Linux](linux-atomic.json) uruchomiła produkcyjny
moduł w istniejącym pinned kontenerze Python 3.11.15, Linux aarch64,
bez sieci, z readonly filesystem i użytkownikiem 65534. Kernel odmówił
nadpisania pustego katalogu i poprawnie opublikował kompletny katalog.
Te same własności przeszły w testach na macOS; pełny pipeline Linux czeka na CI.

Przy równoczesnym eksporcie dwa procesy otrzymują `published` oraz `reused`
z tym samym snapshot ID. Identyczny re-export zachowuje wszystkie bajty
źródła i gotowego katalogu. Inny chunk/partition layout oraz zmienne
generated_at/Git SHA/CSV row order nie zmieniają logicznej identity.
Truth variant lub inny transform pod istniejącym source ID oznacza konflikt.
Nie nadpisuje się nawet uszkodzonego albo pustego destination.

Testy odrzucają corrupted/missing/extra/symlink pliki i katalogi, path traversal,
unsupported major, fake ID, niezgodne typed rows mimo poprawionego byte SHA,
błędne counts i date partitions. Kontrolowana awaria przed rename nie zostawia
gotowego snapshotu. Obsłużone błędy sprzątają staging; twarde przerwanie może
zostawić prywatny katalog do kontrolowanego cleanup.

Default eksportuje 25 tabel faktów/planów/historii. Users, operational outputs,
niekwalifikowane inventory i stare redundantne projekcje są wykluczone.
Opcjonalne cztery truth tabele są wyłącznie w `evaluation_truth` z mode 0700;
nie są montowane w runtime ani dołączane do cech. Nie jest to izolacja między
procesami działającymi jako ten sam użytkownik systemu.

Parquet zachowuje wszystkie źródłowe wersje, quantity null/zero i UTC availability.
Regresje historii potwierdzają, że późna sprzedaż/korekta nie zmienia starego
origin, cech, treningowych labels ani predykcji. Cross-repo odczyt tych gwarancji
zostanie odebrany dopiero po importerze i curated.

## Następny zakres i ograniczenia

Można przejść do **03.3 — mały handoff fixture i kontrakt dla repo AI**.
Następnie 03.4 importer, 03.5 curated i 03.6 bramka cross-repo. Etapy 04 i 06
pozostają zamknięte do odbioru 03.6. Nie wykonano treningu ani integracji DB/AWS.

Data CI ma testy i pełną bramkę obu smoke przez `make data-parquet-check`, timeout
30 minut oraz JUnit/benchmark/Bandit evidence. Weryfikację lokalną wykonano
poleceniami komponentów tego targetu zapisanymi w verification.json.
**Nie uruchomiono zdalnego Required CI ani push/merge tego zakresu.**
Generator i pełna kwalifikacja nadal materializują tabele; ai-dev/ai-training
nie mają odbioru end-to-end na podstawie wyników smoke lub benchmarku writera.
