# Profile danych

Aktualne wartości definiują [generator](../../data/generator/main.py)
i [ustawienia profili](../../data/generator/profile_engine.py).
To profile syntetycznych danych do demonstracji i testów.

| Profil | Historia w dniach | Produkty | Sklepy / miejsca sprzedaży | Magazyny | Domyślny katalog |
|---|---:|---:|---:|---:|---|
| `demo` | Stały scenariusz | Stały scenariusz | Stały scenariusz | Stały scenariusz | `data/demo/` |
| `small` | 90 | 100 | 5 | 3 | `data/synthetic/small/` |
| `medium` | 180 | 500 | 20 | 6 | `data/synthetic/medium/` |
| `large` | 365 | 1 000 | 50 | 10 | `data/synthetic/large/` |

`demo` ignoruje `--days`, `--products`, `--stores` i `--warehouses`, wyświetlając
ostrzeżenie. `small`, `medium` i `large` przyjmują te nadpisania oraz `--seed`
(domyślnie 42). Parametry liczbowe muszą być dodatnie. Profil nie jest gwarancją
stałej liczby transakcji ani kompletnego dziennego panelu ML.

Generator opiera daty na stałej `BASE_DATE=2026-04-30` w
[common.py](../../data/generator/common.py), a nie na bieżącej dacie komputera.
Zakresy poszczególnych tabel mogą wykraczać poza nominalną historię sprzedaży,
np. z powodu zwrotów lub planów cen. Odczytuj rzeczywiste daty z artefaktów;
nie wyznaczaj ich z daty uruchomienia ani dawnego opisu katalogu `small`.

## Zapis i wersjonowanie

- `data/demo/` i referencyjny `data/synthetic/small/` są śledzone w Git.
- `medium`, `large`, `data/generated/` i `data/replay/` są ignorowane.
- Nowy eksperyment zapisuj przez `--output-dir` do osobnego katalogu.
  Wyjątek ignorowania dla `small` obejmuje także nowe podkatalogi, więc duże
  wyniki ML w tym miejscu wymagają świadomego pozostawienia poza commitem.
- Każdy profil zapisuje CSV, `dataset_manifest.json` i `quality_report.json`.
  Profile skalowane zapisują również `realism_report.json`.
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
Profile `ai-smoke`, `ai-dev` i pozostałe z [planu AI](../plans/ai/kontrakty/profile-i-bramki.md)
są propozycją do wdrożenia; obecne CLI ich nie obsługuje.
