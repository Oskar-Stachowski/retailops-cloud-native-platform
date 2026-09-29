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

- `data/demo/` jest śledzone w Git; wszystkie `data/synthetic/`,
  `data/generated/` i `data/replay/` są ignorowane.
- Nowy eksperyment zapisuj przez `--output-dir` do osobnego katalogu.
- [Polityka AI 03.1](parquet-artifacts.md) ogranicza fixtures do 5 MiB po
  rozpakowaniu i najwyżej jednego bieżącego fixture; archiwa regresji zachowujemy.
- Każdy profil zapisuje CSV, `dataset_manifest.json`, `dataset_manifest.v2.json` i `quality_report.json`.
  Profile skalowane zapisują również `realism_report.json`.
- Profile AI zapisują dodatkowo dziewięć kanonicznych tabel CSV i `dimensions_report.json`;
  ich projekcje products/stores/warehouses pochodzą z tych wymiarów.
  Pięć tabel [cen/promocji](retail-pricing.md) i trzy [popytu/panelu](daily-demand.md)
  oraz trzy [zwrotów](retail-returns.md), dwie parametrów symulacji i tabela
  historii obserwacji dają łącznie 40 CSV;
  pricing_report, demand_report, returns_report, source_report i realism_report mają JSON/MD.
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
Profile AI nie rozszerzają listy profili seeda. [AI 03.1](parquet-artifacts.md)
dodaje konwersję do chunked typed Parquet z date partitions i benchmark obu
smoke profili. Generacja źródła nadal buduje tabele w pamięci;
pełnych ai-dev/ai-training nie zmierzono. Kwalifikowany niezmienny eksport
opisuje [AI 03.2](ai-snapshots.md). Importer/curated i
[pełna bramka cross-repo](ai03-cross-repo.md) mają odbiór obu smoke.

## Manifest v2 i identity

V1 zachowuje dotychczasowy format. Aktualną konfigurację odczytuj z
`descriptor.resolved_parameters` w v2: wartości nie są null.
Nowy v2 ma schemat 2.6.0 i generator 0.8.0. Zapisuje wersje konfiguracji,
kalendarza, wymiarów, pricing, demand, returns, simulation, historii obserwacji oraz kanonizacji, requested config,
seed, SHA kodu i przypiętych plików requirements, wersję Pythona oraz commit/stan kodu.
Każdy CSV ma checksumę SHA-256 bajtów, rozmiar i liczbę rekordów oraz osobny
hash kanonicznej treści. Zakresy obejmują wszystkie zadeklarowane pola czasu:
także końce promocji, forecast horizon, przyszłe ceny i zwroty.
Legacy watermarks to granica wiedzy na koniec konfiguracji o 23:59:59 UTC;
complete_through=null oznacza brak gwarancji kompletności. Panel AI ma osobny
watermark następnej północy UTC, complete_through=end_date, dotyczący
syntetycznej sprzedaży. [Zwroty](retail-returns.md) mają osobne cutoffy historii
i 39-dniowego ogona oraz flagi dojrzałości kohort.
Odczyt zachowuje zgodność z rzeczywistymi eksportami schema 2.0.0/generator 0.2.0
oraz 2.1.0/0.3.0, 2.2.0/0.4.0 i 2.3.0/0.5.0 oraz 2.4.0/0.6.0 i 2.5.0/0.7.0;
ich identity nie jest przepisywane. Nowe profile AI wymagają tabel i bramek wymiarów,
a nowe legacy deklarują dimensions, pricing, demand, returns, simulation i historię obserwacji `not_applicable`.

Logical ID to `source-sha256-<hash deskryptora>`. Kanonizacja obejmuje typowane
liczby, null, NFC, UTC i uporządkowany multizbiór zachowujący duplikaty.
Adapter czasu rozpoznaje dawną reprezentację tuple w CSV demo bez zmiany bajtów.
Katalog, ścieżka venv, czas zapisu, własny ID i checksum całego manifestu
nie wchodzą do ID. Treść kodu i zależności wchodzi do ID.
Przestawienie wierszy albo równoważny zapis liczby może zachować hash treści,
ale zmienia checksumę pliku.

Nowe cechy legacy mają schema 2.1, a AI używają [schema 3.1](ml-features.md).
Zachowują feature_manifest.json, otrzymując
`features-sha256-<hash>` zamiast dawnego ID profil/daty/seed.
`feature_identity_manifest.json` zapisuje source parent ID i deskryptor,
hash kontraktu/transformacji oraz checksumę CSV. Historyczne artefakty pozostają
historyczne; nowe eksperymenty budują cechy w nowych katalogach.

Katalog z manifestem v2 można ponowić dla tej samej identity.
Inna identity albo uszkodzony eksport blokuje zapis przed nadpisaniem.
Atomowy pełny snapshot i importer pozostają etapem 03.
Źródło ma `inventory_ready=false`, forecasting/anomaly/stockout/replay `not_ready`,
RAG `not_applicable`. AI deklaruje osobno `source_ready=true` po
[46 bramkach źródła i separacji](source-acceptance.md); legacy ma source_ready=false.
[Odbiór DATA-01](../evidence/ai/02/data01/README.md) potwierdza konfigurację i identity.
[Odbiór DATA-02](../evidence/ai/02/data02/README.md) obejmuje wymiary i kalendarz.
[Odbiór DATA-04](../evidence/ai/02/data04/README.md) obejmuje ceny/promocje i uzgodnienie transakcji.
[Odbiór popytu/panelu/koszyków](../evidence/ai/02/demand-panel/README.md) potwierdza pełny ważny panel i cechy AI 3.0.
[DATA-03](../evidence/ai/02/data03/README.md) obejmuje chronologię i zwroty,
a [DATA-05](../evidence/ai/02/data05/README.md) końcowy odbiór źródła i izolowanego workera.
