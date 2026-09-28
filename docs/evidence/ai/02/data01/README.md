# AI 02 / DATA-01 — konfiguracja i identity

**Odbiór lokalny: 28.09.2026. Repo: RetailOps. Branch: `ai/02-data-01`.**
Implementacja: `bb9333eb337a1b6dfd498d8531fc9657044f8ca9`, baza:
`b8de65b53b3f27863bb11999ca6e9a5d6d41a760`. Odbiór obejmuje wyłącznie pierwszy
zakres etapu 02. Zdalny Required CI tej zmiany: `not_run`.

## Wynik i zgodność

Jedno rozwiązanie konfiguracji zapisuje requested/effective parameters,
jawne daty, rozmiary, seed i limit nominalnej siatki. Profile AI mają stałe
domyślne daty i rozmiary; temporal smoke deklaruje 28/60/14 dni.
Generator 0.2.0 używa jawnego kalendarza legacy UTC i dodaje source manifest
2.0.0 obok v1. [Profile i zasady identity](../../../../reference/data-profiles.md)
opisują obecny interfejs i formaty.

Source ID zależy od efektywnej konfiguracji, treści wszystkich 17 tabel,
wersji, kodu i przypiętych requirements. Feature ID zależy od source parent ID,
kontraktu, transformacji i treści cech; wyklucza własny ID i czas zapisu.
Każdy artefakt ma osobną checksumę bajtów i hash kanonicznej treści.
Manifest v2 opisuje faktyczne daty tabel i pól, history/future ranges oraz
niezamknięte okresy cen. Watermark jest granicą wiedzy, nie maksymalną datą planu;
nie deklaruje kompletności źródła.

V1, CSV demo i schema cech 2.0 zachowują format. Nowe cechy mają ID
`features-sha256-…` oraz dodatkowy `feature_identity_manifest.json`.
Nowy eksperyment buduje cechy w nowym katalogu; dawnych artefaktów RF nie
przepisujemy na nową lineage. Katalog v2 odrzuca inne dane i uszkodzony eksport
przed zapisem. Ta sama identity pozwala ponowić generację.

## Weryfikacja

[verification.json](verification.json) zachowuje polecenia, zakresy i wyniki.
Pełne pytest: **432 passed, 0 skipped**, w tym PostgreSQL, seed/API,
generator, kontrakty i ML. Coverage API **83,82%**, próg 70%.
Ruff, formatowanie, skonfigurowane mypy, Bandit high/high oraz skan patcha
Gitleaks przechodzą. Mypy obejmuje pięć istniejących modułów z konfiguracji;
nie jest pełnym sprawdzeniem typów nowego generatora.

Testy negatywne obejmują null/brak efektywnego parametru, niezgodne daty,
przekroczony limit siatki, niepełny ai-load, zmianę checksumy/treści/ID,
błędny zakres, watermark, provenance, path traversal, brak pliku,
duplikaty kluczy JSON i próbę nadpisania innej identity.
Równoważne liczby/UTC/NFC i inna kolejność rekordów zachowują canonical content;
duplikaty i zmiana wartości zmieniają odpowiedni hash.
Oba CLI walidacji odrzuciły uszkodzone CSV z exit 1 i stałym komunikatem.

[acceptance.json](acceptance.json) pochodzi z implementacji powyższego SHA,
ze stanem kodu generatora `clean`; pozostałe zmiany dokumentacji nie wchodzą
do fingerprintu. Wszystkie dane wygenerowano w usuwanych katalogach temp.

| Próba | Wynik |
|---|---|
| Dwa `ai-smoke` w innych katalogach | Te same source/feature IDs i bajty CSV |
| Dwa `ai-temporal-smoke` w innych katalogach | Te same source/feature IDs i bajty CSV |
| `small`, 90 dni, seed 42, 100 vs 20 produktów | Różne source i feature IDs |
| Legacy demo oraz `small` 14/20/4/3 | Każde 17 CSV zgodne bajtowo z bazą |
| Referencyjne demo w repo | Wszystkie 19 śledzonych plików bez zmian |

Cały sekwencyjny odbiór source/features/validation: **14,46 s**, peak RSS
**111,08 MiB** na macOS ARM64 / Python 3.11.15. To jeden lokalny proces,
bez treningu, importera AI, pobierania zależności ani odbioru budżetu CI etapu 03.
Baseline sum kontrolnych: [legacy-baseline.json](legacy-baseline.json).

## Odtworzenie

Z katalogu głównego repo, po `make api-install`, na zapisanym kodzie:

```bash
PYTHONPATH=. services/api/.venv/bin/python -m scripts.data.verify_data01 \
  --baseline docs/evidence/ai/02/data01/legacy-baseline.json \
  --require-clean --output /tmp/retailops-data01-acceptance.json
```

Polecenie tworzy wyłącznie mały raport; wygenerowane CSV pozostają w temp.
Generowanie i weryfikacja pojedynczego source/feature eksportu:
[instrukcja danych](../../../../guides/data.md).
Pełny pytest wymaga zmigrowanej i zasilonej demo, jednorazowej bazy PostgreSQL;
`REQUIRE_DB_TESTS=1` blokuje ciche pomijanie prób DB. Użyty kontener nie miał
named volume; po próbach został zatrzymany i usunięty.

## Ograniczenia i dalsza praca

Ten pomiar kwalifikuje konfigurację i identity źródła 2.0; nie obejmował
wymiarów, panelu, cen, chronologii/zwrotów ani izolacji procesu.
Bieżący [odbiór źródła 2.6](../data05/README.md) obejmuje te komponenty
oraz bramki do rozpoczęcia AI 03. Modele i inventory pozostają niegotowe.
Aktualny punkt wznowienia: [snapshot i curated 03](../../../../plans/ai/etapy/03-snapshot-curated.md).
