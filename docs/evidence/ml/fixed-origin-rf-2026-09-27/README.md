# Ocena Random Forest z jednego origin — 27.09.2026

**Decyzja lokalna: `rejected`.** Wariant 80 drzew był lepszy od wariantu 20
drzew według średniej WAPE trzech okien walidacyjnych, lecz na odłożonym teście
osiągnął WAPE `159.8564%` wobec `148.1966%` średniej ruchomej. Nie spełnił
warunku poprawy o co najmniej 5% ani limitów regresji MAE w części segmentów.
Wynik nie uprawnia do serving ani do oznaczenia `candidate`/`approved`.

## Konfiguracja i pochodzenie

Wykonano dwa warianty RF (`n_estimators=20` i `80`) z tymi samymi danymi i
oceną. Profil `small` ograniczono do 90 dni, 20 produktów, 5 sklepów i
3 magazynów; seed generatora i `random_state` wynosiły 42. Okno historii to
28 dni, horyzont 7 dni, minimum 7 obserwacji, trzy rozłączne okna walidacyjne
i odłożony test. Zakres danych syntetycznych: 31.01–30.04.2026. Testowe
prognozy dotyczą 24–30.04.2026. Każde okno używa jednego origin o 23:59:59 UTC
dnia przed pierwszym targetem. Oba RF i średnia ruchoma oceniają dokładnie te
same rekordy; [analiza](analysis.json) sprawdza też zgodność wartości rzeczywistych
i prognoz baseline między wariantami.

Źródła treningu: commit `97a4aa6c899fe7c9eb77cb057608a265b06ff980`,
bez niezapisanych zmian w plikach wejściowych. SHA-256 drzewa źródeł:
`1d8d69d94d27f34c5a23d424e952d292ce378d7bfe992aaa4aba71f64d85a38f`.
Środowisko: CPython 3.11.15, macOS arm64, scikit-learn 1.9.1, joblib 1.6.0,
NumPy 2.4.6, SciPy 1.17.1, threadpoolctl 3.7.0. Dwa niezależne venv zbudowano
z `services/api/requirements-dev.txt`; dokładne wersje użyte w przebiegu są
w [manifeście wejść](rf-80-experiment-inputs.json). Wersje przechodnie są tam
zapisane, choć nie wszystkie są przypięte w pliku wymagań.

| Wariant | `run_id` | Średnia WAPE walidacji | Status |
| --- | --- | ---: | --- |
| RF 20 | `d0d250f4951d44abbbaad1b358002f80` | 127.1153% | `rejected` |
| RF 80 | `4d88f7e8e1334360afc0d662b1375b68` | 124.4997% | `rejected` |
| RF 80, osobny venv | `fa1ca9c081db41e1b2d5788d757b7272` | 124.4997% | `rejected` |

Regułą porównania wariantów była niższa średnia WAPE trzech okien
walidacyjnych. Test nie służył do strojenia ani zmiany parametrów po ocenie.
Jest to lokalny eksperyment na syntetycznych danych, a nie ślepy benchmark.

## Wyniki na tych samych rekordach

Każde okno miało 700 uprawnionych i 700 ocenionych rekordów. Sezonowy model
naiwny bierze liczbę sprzedanych sztuk sprzed siedmiu dni, pod warunkiem że
obserwacja była dostępna w origin. W tym przebiegu miał historię dla wszystkich
2800 rekordów. WAPE to metryka główna; MAE, RMSE i bias są w sztukach.

| Okno | RF 20 WAPE | RF 80 WAPE | Średnia ruchoma WAPE | Naiwny sezonowy WAPE |
| --- | ---: | ---: | ---: | ---: |
| Walidacja 1 | 124.5483% | 118.1945% | 123.4564% | 154.1426% |
| Walidacja 2 | 113.6883% | 111.3124% | 111.7036% | 165.3383% |
| Walidacja 3 | 143.1094% | 143.9922% | 128.4157% | 183.5970% |
| Test | 165.1300% | 159.8564% | 148.1966% | 208.6033% |

| Test, 700 rekordów | WAPE | MAE | RMSE | Bias |
| --- | ---: | ---: | ---: | ---: |
| RF 20 | 165.1300% | 60.4329 | 164.6710 | +25.7014 |
| RF 80 | 159.8564% | 58.5029 | 154.4301 | +25.2171 |
| Średnia ruchoma | 148.1966% | 54.2357 | 143.8100 | +8.9929 |
| Naiwny sezonowy | 208.6033% | 76.3429 | 272.1963 | +11.6257 |

MAPE obejmuje jedynie 31,71% rekordów testu z dodatnim popytem; nie jest tu
metryką wyboru. Szczegółowe liczebności, MAPE, zerowe targety, metryki każdego
okna i [próbka prognoz](predictions_sample.csv) są w plikach dowodowych.
Próbka zawiera po trzy rekordy z każdego dnia horyzontu. Pełne prognozy,
panel i modele pozostają w ignorowanych przez Git katalogach przebiegów;
ich sumy logiczne i bajtowe są w manifestach.

Na teście każda kategoria miała 70 lub 105 rekordów. Przykładowo WAPE RF 80
wyniosła 119.0322% dla Home Improvement (baseline 115.7608%), 169.7192%
dla Fashion (baseline 139.2348%) i 187.1818% dla Electronics (baseline
171.9086%). Kanały miały od 140 do 280 rekordów; RF 80 był gorszy od średniej
ruchomej w każdym z czterech kanałów. Każdy z pięciu sklepów miał 140
rekordów; WAPE RF 80 wyniosła od 140.2931% do 173.8387%, a średniej ruchomej
od 133.8772% do 163.0229%. Pełne wyniki dla kategorii, sklepów i kanałów,
z identyfikatorami i liczebnościami, są w [analysis.json](analysis.json).

## Powtórzenie, karta modelu i decyzja

Wariant RF 80 powtórzono w drugim świeżym venv z tymi samymi wersjami
zależności. SHA-256 pliku modelu w obu przebiegach to
`571d1b303e2fe1c11b31ea88b79c100d1e6497d3447cd2e995435192a60667ab`,
a logiczny SHA-256 prognoz to
`51b4900aaa2456e81a4ee7986694f95bad6186d1f62134621ffcc06433e8ba5f`.
Wszystkie prognozy całkowitoliczbowe i metryki oceny są identyczne (tolerancja
0 sztuk). `experiment_id` różni się, bo manifest wejść zawiera bezwzględną
ścieżkę interpretera właściwą dla każdego venv; pozostałe wejścia są identyczne.

Karta ocenionego modelu to [rf-80-model-card.md](rf-80-model-card.md). Artefakt
jest pipeline scikit-learn z `DictVectorizer` i `RandomForestRegressor` oraz
cechami kalendarza, identyfikatorów serii, stałych opisów produktu i sprzedaży
znanej w origin. Nie używa zrealizowanej ceny, nieudokumentowanej promocji,
stockout ani zapasu. Panel opiera się na deklaracji kompletności generatora
syntetycznego. Weryfikator odczytał model i odtworzył dokładnie prognozy
końcowego testu. Lokalna ścieżka batch/metadata/metryk przyjęła ten sam
oceniony przebieg; jej wynik jest diagnostyczny, a status pozostał `rejected`.

Polityka `retailops-forecast-local-v1` zaliczyła protokół, pełne pokrycie,
stabilność walidacji (2 z 3 wygranych) i reprodukcję artefaktu. Odrzuciła
warunek poprawy WAPE na teście (−7,8678% względem średniej ruchomej, przy
wymaganiu +5%) oraz limit MAE w części sklepów i kanałów. Nie podejmowano
dalszego strojenia, aby wymusić pozytywny status.

Historyczny [snapshot v1](../random-forest-v1/README.md) podawał WAPE
72.1146% dla RF i 81.0797% dla baseline. Wykorzystywał poprzedni rolling
holdout, inny zakres wygenerowanych danych oraz starszą wersję modelu.
Różnica liczb między snapshotami nie jest oszacowaniem wpływu samego modelu.

## Pliki i odtworzenie

[rf-20-metrics.json](rf-20-metrics.json),
[rf-80-metrics.json](rf-80-metrics.json) i
[rf-80-repeat-metrics.json](rf-80-repeat-metrics.json) zawierają raporty
metryk i decyzji. [Manifest wybranego przebiegu](rf-80-run-manifest.json)
oraz [manifest powtórzenia](rf-80-repeat-run-manifest.json) podają SHA-256
wszystkich surowych artefaktów, w tym modeli, paneli i pełnych prognoz.
[analysis.json](analysis.json) dokumentuje porównanie na tych samych rekordach
i segmenty. [Manifest batch](rf-80-batch-manifest.json) oraz
[snapshot metryk](rf-80-performance-snapshot.json) wskazują ten sam oceniony
model; są wynikiem lokalnego uruchomienia bez zapisu do API. Plik
[checksums.sha256](checksums.sha256) chroni pliki tego katalogu.

Pełne lokalne artefakty są w
`ci-cd/reports/ml/experiments/small/<run_id>/` i nie są śledzone przez Git.
Dokładne polecenie treningu jest w `reproduction_command` manifestu wejść;
w nowym venv trzeba podstawić jego ścieżkę interpretera. Przykład:

```bash
python3.11 -m venv /private/tmp/retailops-ml-reproduction
/private/tmp/retailops-ml-reproduction/bin/python -m pip install -r services/api/requirements-dev.txt
/private/tmp/retailops-ml-reproduction/bin/python -m ml.models.random_forest_forecast \
  --profile small --days 90 --products 20 --stores 5 --warehouses 3 \
  --seed 42 --window-days 28 --horizon-days 7 \
  --min-history-observations 7 --validation-windows 3 \
  --n-estimators 80 --random-state 42
```

Skrypt [porównania](../../../../scripts/ci/ml_experiment_report.py) weryfikuje
trzy kompletne przebiegi, oblicza sezonowy model naiwny i tworzy analizę.
Ten raport dowodzi lokalnej oceny i odtworzenia, nie działania Prometheus,
produkcyjnego serwowania ani jakości na danych rzeczywistych.
