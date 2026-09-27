# Identyfikacja przebiegów Random Forest — 27.09.2026

Próba techniczna potwierdza przypisanie wyników do kodu, danych, parametrów i
środowiska oraz brak nadpisywania poprzedniego przebiegu. Nie jest oceną jakości
prognoz ani dopuszczeniem modelu. Wszystkie przebiegi używają starego protokołu
`legacy_rolling_holdout_exploratory_only`.

Uruchomiono moduł `ml.models.random_forest_forecast` w `services/api/.venv/bin/python`
z `--profile small --days 8 --products 8 --stores 2 --warehouses 2 --seed 42
--window-days 7 --horizon-days 7 --holdout-days 2 --random-state 42`.
Warianty różniły się wyłącznie `--n-estimators` (20 albo 80). Dokładne
polecenie każdego przebiegu jest w `experiment_inputs.json`.

| Drzewa | `experiment_id` | `run_id` | Logiczny SHA-256 prognoz |
| --- | --- | --- | --- |
| 20 | `rf-abd387beeac86d12a537` | `a12b618b711042fe82faa3fa10335ee9` | `439c75bd8eaada583444d9bc1ebfbcce553989ff3e1f6f0700efcd6702e65555` |
| 20 (powtórzenie) | `rf-abd387beeac86d12a537` | `59913961f0c1499c90d2b670fd0e8a55` | `439c75bd8eaada583444d9bc1ebfbcce553989ff3e1f6f0700efcd6702e65555` |
| 80 | `rf-4b590732ae8fe82aeda2` | `0a9a447045ad43cdaaf0c78a15045518` | `3188005b1d2c11a384b7dca704355cde8177c67590261e4e93db2dfb8c973194` |

Wszystkie trzy przebiegi mają źródłowy SHA-256
`e6170bc50f7c1c2e28ff70ed5b074728476a86762b4d5c62de50873b95ec35e9`,
logiczny SHA-256 tabel generatora
`0bc9d5d82da4b772967ec237d6f8a93054c12aecf84f794c1c7acff49debda8c`
i cech `d7591f58b3f704fb306b86d403be8bff413d0de73fcac64447be376eac56d4b8`.
Kod opierał się na commicie `d7e8725bfb517595d2cefda4d6011f2db70b2aed`
z niezapisanymi zmianami `Makefile`, modelu RF i modułu identyfikacji;
`experiment_source.zip` zachowuje ich dokładną treść. Środowisko:
CPython 3.11.15, Darwin arm64, scikit-learn 1.5.2, joblib 1.4.2,
NumPy 2.4.4, SciPy 1.17.1, threadpoolctl 3.6.0. Są to wersje faktycznie
użyte, odmienne od części przypiętych wymagań repozytorium.

Pełne wyniki lokalne znajdują się w ignorowanym przez Git katalogu
`ci-cd/reports/ml/experiments/small/<run_id>/`. Każdy zawiera manifest
konfiguracji, źródła, model, prognozy, metryki oraz sumy bajtowe plików.
Powtórzenie 20 drzew dało tę samą logiczną sumę prognoz i tę samą bajtową
sumę modelu `185944368ee60bafec00b067b72fee98913a992338cc7ea736e14031ac2ea16b`,
przy odrębnych identyfikatorach przebiegów. Sumy bajtowe innych plików są w
`run_manifest.json` każdego przebiegu; jego sam nie można ująć we własnej sumie.
Historyczny [snapshot v1](random-forest-v1/README.md) pozostał bez zmian.
