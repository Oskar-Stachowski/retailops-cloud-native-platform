# AI 06.6b.2a — wersjonowany source inventory

**Odbiór lokalny 29.09.2026, branch `ai/06-01-inventory-ledger`,
implementacja `f477659`, poprawka i runtime odbioru `5f1b762`.**
[Rejestr](verification.json) przypina pełne SHA, komendy, ID, checksums i wyniki.
Środowisko: macOS ARM64, Python 3.11.15, PyArrow 25.0.1, `services/api/.venv`.
[Kontrakt i uruchomienie](../../../../reference/inventory-source-dataset.md)
opisują source 2.7, generator 0.9 i policy `inventory-source-acceptance-1.0.0`.

## Zakres odbioru

**58 tabel CSV: 46 facts/plans oraz 12 private simulation truth.** Jeden source
łączy rzeczywiste koszyki, ceny i refundy z native inventory/supply/disposition,
ledgerem, snapshotami, popytem i prywatnymi projekcjami stockout.
Financial `return_events` ma jedną kopię, a losowe legacy inventory i outputs
prognoz/anomalii nie są wejściem tego source.
Dzienne ceny, panel, history i cohorts korzystają z causal availability;
transakcje zachowują surowe ingestion. Private config pozostaje poza facts.

Nowe niezmienne `source-sha256-*` wiąże pełną konfigurację/context, schema,
logical table hashes i provenance wykonywanego kodu. Zapis publikuje tylko
zweryfikowany staging; ponowne wykonanie odczytuje istniejący source bez naprawy.
Czytnik sprawdza table/file/column allowlist, grain, typy/nulle, placement,
checksums, ID i provenance, a następnie ponownie wylicza quality/realism.
Nie ufa zapisanym statusom i nie generuje ponownie koszyków sprzedaży.

**36 bramek** obejmuje wymiary, ceny, transakcje i finanse oraz uzgodnienie
native process/projections, `latent = observed + lost`, commerce/issue parity,
pełny historyczny route lineage, konfigurację, private supplier realization,
każde reorder order i initial plan względem znanych faktów w review origin,
causal observation/cohort history i feature projection bez truth.
Poprawka `5f1b762` zachowuje legacy PAIR numbering niezależnie od sortowania CSV.

## Profile i powtarzalność

Oba pełne standardowe profile wykonano dwukrotnie od świeżego generatora,
na czystym runtime przypiętym do commita. Source IDs, descriptors, wszystkie
58 artifact checksums i pełne reports/checks są zgodne w powtórzeniach.

| Profil | Tabele / wiersze | Sold / lost units | Inventory snapshots | Epizody | Czas obu przebiegów |
|---|---|---|---:|---:|---|
| `ai-smoke`: 30 dni, 20 produktów, 3 stores, 2 stock locations | 58 / 51 797 | 5580 / 5467 | 1200 | 189 | 45,34 s / 39,20 s |
| `ai-temporal-smoke`: 102 dni, 8 produktów, 3 stores, 2 stock locations | 58 / 89 836 | 11 333 / 8608 | 1632 | 314 | 82,86 s / 82,82 s |

| Profil | Nowy source ID |
|---|---|
| `ai-smoke` | `source-sha256-47a6607069b8c7d8d5c25300fc237fc649ad6283e426fd41cab1f7b8d11762cd` |
| `ai-temporal-smoke` | `source-sha256-4f1bd330414b9d72626c4b0bac89c07fdc962f8eb9619484f9150c8edd88b4db` |

**8 przypadków rzeczywistego CLI:** cztery pełne przebiegi, supplier-poor,
zero opening, late availability i no demand. Status/exit są zgodne.
Late availability zapisuje poprawny source z `facts_ready=false`, status
`not_ready` i exit 1. Źródło bez popytu ma 0 arrivals/sales/stockout episodes,
dodatni stock i jawne niedojrzałe diagnostyczne okno, bez wymyślonego labelu.

Każdy przebieg generator → source CSV → gates → readback mieści się
w 300 s / 1024 MiB; maksimum 203,17 MiB RSS. Pomiar nie obejmuje nowego
eksportu/importu/curated 03 ani pełnej bramki cross-repo.

## Regresja i próby błędów

- **664 testy `data/tests`, bez błędów i pominięć; 22 nowych.**
  Obejmują schema, roundtrip, świeże powtórzenia, reuse i oba readiness states.
- Cztery zmienione tabele z przeliczonym checksum/content hash/ID są
  odrzucane przez ponowne uzgodnienie: sales, route lineage, daily demand truth
  i supplier sample. Raport ze starym `passed` nie jest dowodem poprawności.
- Odrzucane są extra file, symlink, próba umieszczenia truth w facts,
  fałszywe inventory readiness i duplicate JSON keys. Uszkodzony istniejący
  source nie jest naprawiany; inne opening/supplier/seed nie przechodzą
  z niezmienionymi faktami.
- Ruff check/format przechodzą; mypy obejmuje 40 plików runtime/acceptance.
  Checked-in JSON Schema odpowiada wykonywanemu modelowi.
- Czytniki archiwów 2.0–2.5 zachowują source/feature IDs i parent.
  Świeży 2.6 nadal przechodzi 46 gates; frozen handoff03 jest poprawny.
  **84 śledzone pliki fixtures/handoff/archives** są byte-identical względem
  `68fe5d9`. Demo i bounded legacy small zachowują po 17 CSV;
  19 tracked demo files pozostaje zgodnych z baseline.

Zmiana fingerprintu czytnika może zmienić ID świeżo wygenerowanego 2.6.
Nie nadpisuje archiwów ani przypiętych snapshotów03.

## Pozostałe warunki

`facts_ready` dotyczy wyłącznie lokalnych uzgodnień tego source.
`source_ready=false`, `inventory_ready=false`, `model_ready=false`,
`publication_status=awaiting_ai03_handoff`; kwalifikacja lifecycle/labels
ma `not_evaluated`. DATA-06 i pełny AI 06 pozostają otwarte.

Najbliższe 06.6b.2b kwalifikuje lifecycle/coverage w fizycznym inventory grainie
oraz dojrzałe okna 08. Następnie 06.6b.2c rozszerzy exporter/importer/curated 03,
typed parity i truth isolation, odbierze nowy snapshot i pełny budżet cross-repo
oraz przełączy domyślną ścieżkę AI na 2.7. Obecne generator/API/03 nadal używają2.6.
Reevaluation04/05 użyje nowych IDs i zgodnego feature schema.
To nie kwalifikacja modelu 08 ani aktualizacja wcześniejszych metryk.

Repo AI i worktree AI 12 nie były modyfikowane. Commity są lokalne na branchu AI 06;
nie wykonano nowego Required CI ani publikacji AI 06 na main/origin.
Pełne artefakty/JUnit/receipts pozostają pod ignorowanym `ci-cd/reports/data/ai06-06b2a/final/`.
Git przechowuje mały rejestr, kontrakt, kod, testy i dokumentację.
