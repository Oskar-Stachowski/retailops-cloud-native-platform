# 03. Zbuduj snapshot, importer i curated

**Status: odebrany lokalnie i w Required CI, opublikowany na main obu repo przez osobne PR-y. Repo: RetailOps + AI. Następne zakresy: 04 i 06 równolegle. Zależność: 02.**

Cel: zbudować powtarzalną granicę między dwoma repozytoriami. Pierwsza ścieżka to lokalny niezmienny eksport plików; kompletny REST/event integration powstaje w etapie 10. Ani działająca baza RetailOps, ani broker, ani AWS nie są wymagane do importu pierwszego snapshotu.

Normatywne dokumenty: [dane i czas](../kontrakty/dane-i-czas.md), [profile i bramki](../kontrakty/profile-i-bramki.md), [architektura](../architektura.md), [szablony evidence](../szablony/karty-i-evidence.md). Warunek wejścia: źródłowe bramki 02 i zadeklarowana wersja kontraktu. Stage03 przyjmuje `inventory_ready=false`; nie wymusza sztucznych stockout/anomaly labels.

[Audyt wejścia](../../../evidence/ai/02/audit/README.md) potwierdza gotowość
źródła 2.6. Fingerprint obejmuje cały wykonywany bundle; historia ilości jest
append-only i odczytywana według stanu znanego w origin. Eksport, importer i
curated mają zachować te gwarancje oraz brak historii zgłaszać jawnie.

[Evidence 03.1](../../../evidence/ai/03/03.1/README.md) i
[aktualny runbook formatu](../../../reference/parquet-artifacts.md) opisują
40 typed tabel, porcje/partycje, checksums/parity, politykę Git i cleanup.
Zapis ma jawne `snapshot_ready=false`; odbiór 03.1 nie otwiera jeszcze 04/06.
[Evidence 03.2](../../../evidence/ai/03/03.2/README.md) i
[runbook snapshotów](../../../reference/ai-snapshots.md) opisują istniejący
`python -m data.export.ai_snapshot`: allowlistę, przeliczone bramki, atomową
publikację, pełną walidację i niezmienny re-export. To lokalny odbiór eksportera.
[Handoff 03.3](../../../reference/source-snapshot-handoff.md) dodaje jeden
samowystarczalny fixture, schema/expected manifest i niezależny checker w repo AI.
[Evidence](../../../evidence/ai/03/03.3/README.md) rozróżnia odbiór kontraktu
i transportu od typed importu i curated.
[Odbiór 03.4](../../../evidence/ai/03/03.4/README.md) dodaje niezależny importer
Parquet, pełne byte/canonical checks, atomową publikację i idempotencję w AI.
[Odbiór 03.5](../../../evidence/ai/03/03.5/README.md) obejmuje curated,
normalizację, jawne mappings, quarantine i as-of z pełnej historii wersji.
[Końcowy odbiór 03.6](../../../evidence/ai/03/03.6/README.md) potwierdza
pełny cross-repo flow, powtórzenia, zasoby i Required CI obu repo.
[Runbook](../../../reference/ai03-cross-repo.md) opisuje odtworzenie;
[karta](../../../evidence/ai/03/03.6/dataset-card.md) określa dopuszczone dane.
Poniższy kontrakt pozostaje instrukcją utrzymania i ponowienia po 06/07.

## Kolejność małych PR-ów

1. **RetailOps — Parquet i polityka artefaktów.** Typed Parquet przez jawną grupę zależności, date partitions dla dużych faktów, chunked writes, CSV compatibility dla demo/fixture. Layout rozdziela facts, truth, raw events, reports, manifests. Git śledzi demo i najwyżej jeden mały fixture; generated exports ignored. Cleanup weryfikuje root i odmawia kasowania tracked fixture. Benchmark mierzy czas, peak RSS, rows/s, bytes oraz rzeczywisty limit CI.
2. **RetailOps — niezmienny exporter.** Zaimplementować np. `python -m data.export.ai_snapshot` jako planowany interfejs; końcowy runbook ma podawać faktycznie istniejącą komendę. Wejściem jest jawny dataset ID albo config/profile/seed/end date. Eksporter wybiera allowlist źródłowych faktów, opcjonalne evaluation truth w odrębnej przestrzeni, schematy i reports. Waliduje manifest, kontrakty i hard gates wymagane dla zadeklarowanych use cases; zapisuje atomowo i weryfikuje checksums po zapisie. Zwraca source dataset ID i pełny manifest.
3. **Kontrakt cross-repo.** Mały samowystarczalny fixture + schema + expected manifest, bez skopiowanego generatora. Dokument handoff opisuje wersje, pola, grain, location mapping, strefy, date ranges i readiness. Zmiany w upstream i consumer mają osobne commity/PR-y i wspólną wersję kontraktu. Wersje major spoza wspieranej listy odrzucane.
4. **AI — importer.** Typed CLI sprawdza kompletność manifestu, wersje, brak niebezpiecznych ścieżek, klasyfikacje, wszystkie byte checksums i zgodność canonical hashes. Publikuje pod `data/generated/snapshots/<source_dataset_id>/`. Ten sam dataset importuje idempotentnie; ten sam ID z różną treścią odrzuca. Nie importuje po cichu źródłowych AI outputs jako facts; truth nie jest automatycznie dostępna aplikacji.
5. **AI — curated builder.** Normalizuje typy, UTC/business dates, jednostki/waluty i słowniki, rekoncyliuje grain oraz mapping. Zachowuje availability i wersje korekt. Materiał odrzucony trafia do jawnej kwarantanny z reason/lineage; nie naprawia go przez losowe zero/warehouse/store. Tworzy immutable Parquet i manifest `curated_dataset_id`, parent source, transform SHA, lock/config hash, counts, rejected/quarantine, classification, checksums, time semantics i readiness.
6. **Bramka cross-repo.** Uruchomić generator → reports → export → import → curated na obu smoke profilach, dwukrotnie. Dopiero wtedy otworzyć zadania 04 i 06. Zmierzyć format CSV/Parquet parity oraz performance; zakres wykonania to przygotowanie danych, bez treningu modeli w tym PR.

## Kontrakt publikacji i zawartości

Manifest podaje source repo/commit, generator/calendar/contract versions, seed, requested/effective config, watermark per stream, rows i zakres dat per artefakt, grain, file size, byte checksum, logical content hash, classification i statusy quality/realism/ML-readiness. Identity descriptor nie zawiera własnego ID ani zmiennych dat/ścieżek wykonania. Źródłowe fakty i evaluation truth mają oddzielne references/uprawnienia.

Zapis tymczasowy jest niewidoczny jako gotowy snapshot. Dopiero poprawne zakończenie gates i checksums publikuje całość. Przerwany eksport/import zostawia niewidoczny staging, który można posprzątać kontrolowanym cleanup. Ponowny run nie nadpisuje immutable artefaktu. Nie umieszczać sekretów, poświadczeń bazy ani danych osobowych użytkowników w snapshotcie.

Historia nie jest „najnowszą tabelą”: wybranie stanu dla origin respektuje wersje i `available_at`. Curated może zawierać późniejsze wersje, ale historyczny odczyt nie może ich widzieć. Dla źródeł bez niezbędnej historii zgłosić ograniczenie; nie deklarować retrospective PIT correctness na podstawie samej daty zdarzenia.

## Kontrole wymagane i negatywne

- Import prawidłowego fixture i identyczny reimport; źródłowy/gotowy katalog oraz checksum nie zmieniają się.
- Corrupted byte, missing artifact, unsupported major, fałszywy ID, path poza root i różna treść pod istniejącym ID są odrzucane przed publikacją.
- Celowo failed source hard gate blokuje eksport. `stockout=not_ready` nie blokuje forecast-only export, ale taki snapshot jest odrzucany przez przyszły job wymagający stockout.
- CSV i Parquet mają te same logiczne wiersze, typy/wartości, nie tylko taką samą liczbę. Inny podział na pliki/partycje zachowuje canonical content hash.
- Dwa pełne przebiegi dają te same source/curated IDs; zmiana liczby produktów, konfiguracji lub transformacji zmienia odpowiednie ID. `generated_at` i lokalny katalog nie zmieniają logicznej identity.
- Brak mappingu lub data-gap nie dostają losowej lokalizacji/zera. Late correction pozostaje nową wersją; odtworzenie starego origin zwraca stare cechy.
- Import truth nie tworzy dostępu w runtime ani automatycznego joinu w feature builderze. AI nie ma ścieżki bezpośredniego odczytu DB RetailOps.
- Cleanup nie usuwa plików spoza generated root ani tracked fixture. Duże wygenerowane dane nie trafiają do Git.

## Artefakty i Definition of Done

Exporter i importer, schema/fixture contract, curated builder, manifesty, policy checks, benchmark, dataset card, tabela counts/date ranges/checksums i dokładny runbook. Przykład evidence ma source SHA obu repo oraz statusy oddzielnie dla use cases. Przy końcu03 forecasting może być gotowy źródłowo; anomaly/stockout czekają na06/07/08.

Ponownie wykonać tę samą ścieżkę po06 (ledger) i07 (injekcje). Nowy source process tworzy nowe source/curated IDs, a forecast wymaga re-ewaluacji na nowych danych przed downstream wykorzystaniem. Nie modyfikować snapshotu z pierwszego eksperymentu.

## Prompt dla Codex

```text
Wykonaj etap03 według etapy/03-snapshot-curated.md, osobnymi PR-ami w RetailOps i AI.
Przeczytaj README.md, architektura.md, kontrakty/dane-i-czas.md,
kontrakty/profile-i-bramki.md i szablony/karty-i-evidence.md oraz evidence02.
Najpierw przygotuj Parquet/identity/immutable export i mały kontraktowy fixture upstream,
następnie typed import oraz curated downstream. Nie kopiuj generatora, nie czytaj DB
RetailOps, nie traktuj forecasts/anomalies demo jako etykiet. Nie wymagaj ledgeru06
dla forecast-only snapshot; deklaruj readiness oddzielnie i wyłącz inventory features.
Obsłuż idempotency, checksum failure, unsupported version, conflict ID i atomową publikację.
Uruchom oba smoke profile oraz powtórzenie całego przepływu, zmierz zasoby i zapisz
wykonane polecenia, manifests, counts, hash lineage, testy i ograniczenia.
Nie wdrażaj AWS ani brokera i nie trenuj modeli w tych PR-ach.
```
