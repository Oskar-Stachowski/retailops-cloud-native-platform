# Praca z danymi

[Generator](../../data/generator/main.py) buduje syntetyczne dane handlowe:
produkty, użytkowników, sklepy, magazyny, zamówienia i pozycje, ceny i promocje,
sprzedaż, zapas, ruchy magazynowe, zwroty oraz dane demonstracyjnych prognoz,
anomalii, alertów i workflow. Wyniki służą lokalnemu demo, testom i eksperymentom.

[Profile danych](../reference/data-profiles.md) podają aktualne rozmiary,
domyślne katalogi i zasady wersjonowania. [Kontrakt seed](../reference/data-contracts.md)
opisuje format wejściowy API. Domyślnym profilem generatora jest `demo`,
a domyślnym profilem loadera bazy — `small`.

## Generowanie

Uruchamiaj z katalogu głównego repozytorium, po przygotowaniu środowiska przez
`make api-install`. Poniższy przykład tworzy własny niewielki zbiór:

```bash
data_run_dir=$(mktemp -d /tmp/retailops-data.XXXXXX)
services/api/.venv/bin/python -m data.generator.main \
  --profile small --days 14 --products 20 --stores 4 --warehouses 3 \
  --seed 42 --output-dir "$data_run_dir"
```

Bez `--output-dir` generator zapisuje `demo` w `data/demo/`, a profil skalowany
w `data/synthetic/<profile>/`. `demo` ma stały scenariusz i ignoruje opcje rozmiaru.
`make data-generate` regeneruje właśnie referencyjne `data/demo/`.
Dane skalowane, w tym `small`, są ignorowane przez Git. Demo pozostaje śledzone.

Każdy przebieg dodaje `dataset_manifest.v2.json` obok dotychczasowego manifestu
i raportu jakości; wszystkie profile skalowane mają też `realism_report.json`.
V2 opisuje efektywną konfigurację, source ID, hashe oraz rzeczywiste daty tabel.
Domyślny koniec profili AI to `2026-07-31`, legacy — `2026-04-30`.
Datę można zmienić jawnie; generator nie używa dzisiejszej daty komputera.

Eksport AI do typed Parquet, układ facts/truth/reports/manifests, benchmark
i bezpieczny cleanup opisuje [runbook AI 03.1](../reference/parquet-artifacts.md).

Przykład profilu AI z kontrolą integralności źródła i cech:

```bash
docker pull python@sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff
data_ai_dir=$(mktemp -d /tmp/retailops-ai-smoke.XXXXXX)
services/api/.venv/bin/python -m data.generator.main \
  --profile ai-smoke --end-date 2026-07-31 --output-dir "$data_ai_dir"
services/api/.venv/bin/python -m data.generator.manifest_v2 --data-dir "$data_ai_dir"
services/api/.venv/bin/python -m ml.features.demand_forecast \
  --profile ai-smoke --end-date 2026-07-31 --source-dir "$data_ai_dir" \
  --output-dir "$data_ai_dir/features"
services/api/.venv/bin/python -m ml.features.identity --data-dir "$data_ai_dir/features"
```

Walidatory kończą się błędem dla niespójnej konfiguracji, identity lub checksumy.
W profilach AI dodatkowo sprawdzają [kanoniczne wymiary, kalendarz i lifecycle](../reference/retail-dimensions.md).
Osiem hard gates zapisuje wynik w `dimensions_report.json`; brak wymaganego dnia,
SKU z whitespace, nieznany magazyn lub sprzedaż poza asortymentem blokuje eksport.
Sześć kolejnych bramek [cen/promocji](../reference/retail-pricing.md) weryfikuje
coverage, znane wersje/scope, transakcje i realized price aggregates oraz kierunek
truth pre/post. Wynik pricing_report ma JSON i krótkie MD. Brak ceny, overlap,
błędny rabat albo nieaktywna promocja kończy się błędem, także w feature builderze.
Sześć bramek [popytu/panelu](../reference/daily-demand.md) sprawdza pełną siatkę,
agregaty, koszyki bez powtórzeń SKU, dzienne budżety i kompletność. Brak dnia,
podwójna waga popytu albo nieuzgodniony koszyk blokuje eksport; missing jest unknown.
Demand report ma JSON/MD, a cechy AI schema 3.1.
Siedem bramek chronologii/zwrotów i trzy kontrole separacji domykają
[46 bramek źródła](../reference/source-acceptance.md). `source_report.json/md`
kwalifikuje AI do snapshotu 03, a `realism_report.json/md` pokazuje diagnostykę
z jawnymi progami i nieocenialnymi metrykami. `source_ready=true` dotyczy źródła;
modele i inventory zachowują `not_ready`. Cechy AI wymagają jawnego
`--source-dir` i lokalnego Dockera z przypiętym obrazem; worker widzi tylko
projekcje faktów. Nie generuje źródła we własnym procesie.
Inne parametry lub zmieniony kod wymagają nowego katalogu,
jeżeli obecny zawiera manifest v2.

## Kontrole danych

```bash
make data-quality
make data-contracts
make data-scenario-report
```

`data-quality` generuje domyślnie `small` pod
`ci-cd/reports/data/generated/small/` i wymaga statusu `passed` raportu jakości.
Przed generacją usuwa wskazany `DATA_OUTPUT_DIR`; przy nadpisywaniu tej zmiennej
wybierz wyłącznie katalog wynikowy tego zadania.
`data-contracts` sprawdza `data/demo/` i kontrakt zdarzeń,
a `data-scenario-report` sprawdza pokrycie scenariuszy demo.

Kontrole strukturalne obejmują m.in. klucze, relacje, wartości, sumy zamówień
i limity zwrotów. Ich przejście nie dowodzi kompletności panelu dziennego,
braku użycia przyszłych informacji ani pełnej zgodności symulacji handlu i zapasu.
Aktualne ograniczenia i kryteria poprawek są w [otwartych ustaleniach](../audits/open-findings.md).

## Ładowanie do lokalnego PostgreSQL

Po uruchomieniu bazy i migracjach wybierz **jedno** polecenie:

| Polecenie | Dane |
|---|---|
| `make api-seed-demo` | `data/demo/` |
| `make api-seed-small` | `data/synthetic/small/`; generuje brakujące pliki na świeżym checkoutcie |
| `make api-seed-medium` | `data/synthetic/medium/`, po wygenerowaniu |

`make api-seed` jest aliasem `api-seed-small`. Loader czyści tabele aplikacji
i w jednej transakcji ładuje CSV w kolejności zależności; to zastąpienie danych,
a nie dopisanie rekordów. Sprawdź docelowy `DATABASE_URL` przed uruchomieniem.
Konfigurację bazy opisuje [lokalne uruchomienie](local-development.md).

Do niestandardowego zbioru użyj zmiennej `RETAILOPS_SEED_DATA_DIR` i loadera
`services/api/scripts/seed_demo_data.py`. Generator i loader są osobnymi
operacjami: wygenerowanie CSV nie zmienia bazy.

## Zdarzenia do replay

```bash
services/api/.venv/bin/python -m data.generator.realtime \
  --profile small --days 7 --products 20 --stores 4 --warehouses 3 \
  --seed 42 --max-events 500
```

Wyniki `events.jsonl` i `event_manifest.json` trafiają domyślnie do
`data/replay/<profile>/`, poza Git. Domyślny limit to 1 000 zdarzeń;
`--max-events 0` wyłącza limit. Generacja pliku nie publikuje go automatycznie
w brokerze. Polecenia brokera opisuje [lokalne uruchomienie](local-development.md),
a zachowanie ML — [instrukcja ML](ml.md).
