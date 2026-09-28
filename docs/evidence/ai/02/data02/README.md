# AI 02 / DATA-02 — wymiary, lifecycle i kalendarz

Odbiór lokalny **2026-09-28**, branch `ai/02-data-02`, kod
`a050e488e5ea5a93b21b5b4d2f678c195ac26cca`, baza DATA-01 `4d57655`.
Zakres: punkt 2 [instrukcji etapu 02](../../../../plans/ai/etapy/02-dane-sprzedazowe.md).
Etap 02 pozostaje w realizacji; następne są wspólne ceny i promocje DATA-04.

## Zachowanie i kontrakty

Profile AI mają dziewięć nowych tabel: katalog kategorii/produktów, selling/stock
locations, wersje assignments/routing/assortment oraz kalendarz par i kategorii.
SKU `sku-1.0.0` ma regex bez whitespace (Pet Care: PETC), marka jest osobna od
kategorii, kanał od regionu. Katalog ma hierarchy, opakowanie, syntetyczny koszt,
margin band i lifecycle. Legacy products/stores/warehouses są adapterem tych tabel.
Pełna specyfikacja: [wymiary](../../../../reference/retail-dimensions.md).

| Kontrakt | Obecne zachowanie |
|---|---|
| Generator / source schema | 0.3.0 / 2.1.0; 26 tabel AI, 17 tabel legacy. |
| Wymiary | retail-dimensions-1.0.0; schema stringowych komórek CSV i osiem hard gates. |
| Kalendarz | pl-de-berlin-calendar-1.0.0, PL i Berlin 2024–2027, jawna syntetyczna polityka otwarcia; inny rok/jurysdykcja jest błędem. |
| Czas | Business date UTC; osobne lokalne granice doby Europe/Warsaw/Berlin uwzględniają DST. Okresy wersji i lifecycle mają wyłączny koniec. |
| Identity | Nowa treść, kolumny i wersje wchodzą do source ID; feature parent wskazuje ten source. Kanonizacja 1.1.0. |
| Odczyt historyczny | Rzeczywiste source 2.0 i feature sidecar z DATA-01 odczytane bez zmiany IDs/parent. |
| Demo i legacy | 17 CSV demo i ograniczonego small zgodne bajtowo z bazą; 19 śledzonych plików demo niezmienionych. |

## Wykonane próby

[acceptance.json](acceptance.json) zawiera sześć przebiegów z czystego kodu:
dwa ai-smoke, dwa ai-temporal-smoke, siedem dni z wiosennym DST i wszystkimi
czterema kanałami oraz 15 dni przez święta grudniowe/Nowy Rok. Powtórzone profile
dają identyczne source/feature IDs, CSV i raporty wymiarów. Wszystkie mają osiem
hard gates passed; dane generowano w temp, bez dużych eksportów w Git.

| Profil | Nominalna siatka | Ważne dni asortymentu | Dni kalendarza par | Wiersze cech legacy |
|---|---:|---:|---:|---:|
| ai-smoke | 1 800 | 1 612 | 90 | 639 |
| ai-temporal-smoke | 2 448 | 2 406 | 306 | 852 |

Ważne dni asortymentu są liczone przed ograniczeniem otwarcia; liczba cech jest
liczbą sparse obserwacji, nie pokryciem pełnego panelu. Sekwencyjny odbiór trwał
4,72 s przy peak RSS 43,31 MiB. To pomiar małych źródeł/cech/walidacji na macOS,
bez treningu i bez benchmarku pełnego ai-training.

[verification.json](verification.json) zapisuje 485 testów, 0 failures/errors/skips,
łącznie z PostgreSQL i API; coverage API 83,82% przy progu 70%.
Po końcowej poprawce metadanych planów wykonano dodatkowo 96 testów źródła/identity.
53 testy wymiarów obejmują pozytywne/negatywne relacje, lifecycle, routing,
available/effective time, oba DST w obu strefach i reguły PL/DE-BE.
Usunięcie dnia, powtórzony SKU, brak magazynu/routingu, overlap, niezgodny adapter
i sprzedaż przed launch/po discontinue/w zamknięciu są odrzucane.
Przeliczenie hashów eksportu z luką kalendarza nie omija kontroli semantycznej.

Ruff, format, skonfigurowane mypy (5 modułów API), Bandit high/high i Gitleaks
przechodzą. Cztery poprawne polecenia source/feature CLI kończą się 0,
a uszkodzone CSV kalendarza/cech i nieobsługiwany rok kończą się 1.
Migracje i świeży seed demo wykonano na odizolowanym PostgreSQL 16;
tymczasowy kontener został usunięty. Zdalnego CI dla tego brancha nie uruchamiano.

## Odtworzenie

Z repo z przygotowanym środowiskiem API, na wskazanej rewizji:

```bash
services/api/.venv/bin/python -m scripts.data.verify_data02 \
  --output /tmp/retailops-data02-acceptance.json \
  --baseline docs/evidence/ai/02/data01/legacy-baseline.json --require-clean
PYTHONPATH=.:services/api services/api/.venv/bin/python -m pytest \
  services/api/tests/test_data_dimensions.py services/api/tests/test_data_identity_v2.py -q
```

Pełne testy wymagają świeżej bazy z migracjami i seedem demo; dokładne polecenie
i parametry izolacji znajdują się w verification.json. Readiness forecasting,
anomaly, stockout i replay pozostaje not_ready, inventory_ready=false.
Pełny daily panel, ceny/promocje, popyt/koszyki, chronologia/zwroty i separacja
truth wymagają dalszych zakresów przed AI 03. Routing jest planem, bez ledgeru AI 06.
