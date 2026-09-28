# Profile danych

Aktualne wartości definiują [generator](../../data/generator/main.py)
i [konfiguracja 1.0.0](../../data/generator/configuration.py).
To profile syntetycznych danych do demonstracji i testów.

| Profil | Historia w dniach | Produkty | Sklepy legacy / ważne pary AI | Magazyny | Domyślny katalog |
|---|---:|---:|---:|---:|---|
| `demo` | Stały scenariusz | Stały scenariusz | Stały scenariusz | Stały scenariusz | `data/demo/` |
| `small` | 90 | 100 | 5 | 3 | `data/synthetic/small/` |
| `medium` | 180 | 500 | 20 | 6 | `data/synthetic/medium/` |
| `large` | 365 | 1 000 | 50 | 10 | `data/synthetic/large/` |
| `ai-smoke` | 30 | 20 | 3 | 2 | `data/synthetic/ai-smoke/` |
| `ai-temporal-smoke` | 102 | 8 | 3 | 2 | `data/synthetic/ai-temporal-smoke/` |
| `ai-dev` | 365 | 100 | 5 | 3 | `data/synthetic/ai-dev/` |
| `ai-training` | 730 | 200 | 10 | 4 | `data/synthetic/ai-training/` |
| `ai-load` | Jawne | Jawne | Jawne | Jawne | `data/synthetic/ai-load/` |

`demo` ignoruje rozmiary, limit siatki i seed, wyświetlając ostrzeżenie;
zachowuje stały scenariusz i seed 42. Profile skalowane przyjmują nadpisania oraz `--seed`
(domyślnie 42). Parametry liczbowe muszą być dodatnie. Profil nie jest gwarancją
stałej liczby transakcji ani kompletnego dziennego panelu ML.

Domyślny koniec legacy to `2026-04-30`, profili AI — `2026-07-31`.
Bez początku start wynika z końca minus `days - 1`. CLI przyjmuje
`--start-date` i `--end-date`; granice są włączne. Sam początek wyznacza koniec
według liczby dni. Obie daty bez `--days` wyznaczają liczbę dni;
z jawnym `--days` muszą być zgodne. Demo odrzuca daty inne niż stały zakres
sprzedaży `2026-04-27`–`2026-04-30`.

`ai-temporal-smoke` deklaruje 28 dni warmup, 60 dni originów i 14 dni tail;
override dni zmienia część originów, minimum to 43 dni. To metadane konfiguracji,
nie ocena modelu. Profile AI używają [wymiarów i kalendarza PL/DE-BE](retail-dimensions.md)
w latach 2024–2027, UTC oraz jawnych flag otwarcia. Profile legacy zachowują
`legacy-weekday-seasonality-1.0.0`. `--stores` w AI liczy ważne pary
selling location/channel; fizycznych miejsc może być mniej niż par.

`ai-load` wymaga czterech rozmiarów oraz `--max-daily-rows`.
Limit sprawdza iloczyn dni × produktów × sklepów przed generacją.
Dla innych profili domyślny limit jest równy temu iloczynowi; można podać własny.
To limit nominalnej siatki, nie orders/items ani dowód kompletnego panelu.
Zakresy poszczególnych tabel mogą wykraczać poza nominalną historię sprzedaży,
np. z powodu zwrotów lub planów cen. Odczytuj rzeczywiste daty z artefaktów;
nie wyznaczaj ich z daty uruchomienia ani dawnego opisu katalogu `small`.

## Zapis i wersjonowanie

- `data/demo/` i referencyjny `data/synthetic/small/` są śledzone w Git.
- `medium`, `large`, `data/generated/` i `data/replay/` są ignorowane.
- Nowy eksperyment zapisuj przez `--output-dir` do osobnego katalogu.
  Wyjątek ignorowania dla `small` obejmuje także nowe podkatalogi, więc duże
  wyniki ML w tym miejscu wymagają świadomego pozostawienia poza commitem.
- Każdy profil zapisuje CSV, `dataset_manifest.json`, `dataset_manifest.v2.json` i `quality_report.json`.
  Profile skalowane zapisują również `realism_report.json`.
- Profile AI zapisują dodatkowo dziewięć kanonicznych tabel CSV i `dimensions_report.json`;
  łącznie 26 tabel. Ich projekcje products/stores/warehouses pochodzą z tych wymiarów.
- `row_counts` i raporty konkretnego wykonania opisują jego zawartość.
  Stała nazwa profilu ani sam seed nie identyfikują wszystkich parametrów.

## Profile ładowania bazy

Loader [seed_demo_data.py](../../services/api/scripts/seed_demo_data.py) obsługuje
`demo`, `small` i `medium`; domyślnie wybiera `small`. To osobne ustawienie od
CLI generatora, które domyślnie wybiera `demo`.
`RETAILOPS_SEED_DATA_PROFILE` wybiera profil, a `RETAILOPS_SEED_DATA_DIR` pozwala
wskazać własny katalog CSV. `large` nie jest obsługiwanym profilem loadera.
Loader zastępuje zawartość tabel aplikacji danymi z wybranego katalogu.

Instrukcje generowania i ładowania: [praca z danymi](../guides/data.md).
Profile AI nie rozszerzają listy profili seeda. Duże profile nadal używają
pamięci i CSV; chunked Parquet i pełny benchmark pozostają do wdrożenia.

## Manifest v2 i identity

V1 zachowuje dotychczasowy format. Aktualną konfigurację odczytuj z
`descriptor.resolved_parameters` w v2: wartości nie są null.
Nowy v2 ma schemat 2.1.0 i generator 0.3.0. Zapisuje wersje konfiguracji,
kalendarza, wymiarów oraz kanonizacji, requested config,
seed, SHA kodu i przypiętych plików requirements, wersję Pythona oraz commit/stan kodu.
Każdy CSV ma checksumę SHA-256 bajtów, rozmiar i liczbę rekordów oraz osobny
hash kanonicznej treści. Zakresy obejmują wszystkie zadeklarowane pola czasu:
także końce promocji, forecast horizon, przyszłe ceny i zwroty.
Watermark to granica wiedzy na koniec konfiguracji o 23:59:59 UTC;
`complete_through=null` oznacza brak gwarancji kompletności.
Odczyt zachowuje zgodność z rzeczywistymi eksportami schema 2.0.0/generator 0.2.0;
ich identity nie jest przepisywane. Nowe profile AI wymagają tabel i bramek wymiarów,
a nowe legacy deklarują dimensions `not_applicable`.

Logical ID to `source-sha256-<hash deskryptora>`. Kanonizacja obejmuje typowane
liczby, null, NFC, UTC i uporządkowany multizbiór zachowujący duplikaty.
Adapter czasu rozpoznaje dawną reprezentację tuple w CSV demo bez zmiany bajtów.
Katalog, ścieżka venv, czas zapisu, własny ID i checksum całego manifestu
nie wchodzą do ID. Treść kodu i zależności wchodzi do ID.
Przestawienie wierszy albo równoważny zapis liczby może zachować hash treści,
ale zmienia checksumę pliku.

Nowe cechy zachowują schema 2.0 i `feature_manifest.json`, otrzymując
`features-sha256-<hash>` zamiast dawnego ID profil/daty/seed.
`feature_identity_manifest.json` zapisuje source parent ID i deskryptor,
hash kontraktu/transformacji oraz checksumę CSV. Historyczne artefakty pozostają
historyczne; nowe eksperymenty budują cechy w nowych katalogach.

Katalog z manifestem v2 można ponowić dla tej samej identity.
Inna identity albo uszkodzony eksport blokuje zapis przed nadpisaniem.
Atomowy pełny snapshot i importer pozostają etapem 03.
Źródło ma `inventory_ready=false`, forecasting/anomaly/stockout/replay `not_ready`,
RAG `not_applicable`; nadal zawiera sparse panel i mixed simulation truth.
[Odbiór DATA-01](../evidence/ai/02/data01/README.md) potwierdza konfigurację i identity.
