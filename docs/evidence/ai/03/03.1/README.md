# AI 03.1 — Parquet i polityka artefaktów

**Odbiór lokalny: 28.09.2026.** RetailOps, branch `ai/03-01-parquet`,
implementacja `439d1c05600cd07fadc604f2dd50a20f45aa726e` na bazie
main `adbed9d`. Zakres: typed Parquet, porcje/partycje, parity, układ plików,
Git/fixtures, bezpieczny cleanup i wykonywalna bramka zasobów.
[Runbook](../../../../reference/parquet-artifacts.md) podaje istniejące komendy.
[Rejestr weryfikacji](verification.json) opisuje zakres testów i ograniczenia.

## Wyniki

**72 testy passed:** 33 formatu/polityki/seed oraz 39 zgodności generatora,
legacy seed, kontraktów, JSON schemas i kanonizacji. Ruff check/format,
Bandit high/high, Gitleaks staged i diff check przeszły.
Wykonano target `make data-parquet-check` z pominięciem już zainstalowanych
prerequisites: `make -o api-install -o data-parquet-install data-parquet-check`.

[Benchmark](benchmark.json) obejmuje oba kompletne profile, każdy dwukrotnie,
w świeżych procesach: generacja/CSV → Parquet → odczyt i porównanie wszystkich
40 tabel. Seedy 42, end date 2026-07-31, chunk 8192, Python 3.11.15,
PyArrow 25.0.1, macOS arm64. Counts obejmują facts, truth i operational outputs.

| Profil | Wiersze wszystkich tabel | Czas pełnego runu | Max peak RSS | CSV bytes | Parquet bytes |
|---|---:|---:|---:|---:|---:|
| ai-smoke | 39992 | 15,16–17,83 s | 120,59 MiB | 9289735 | 1814724 |
| ai-temporal-smoke | 67878 | 38,00–38,04 s | 147,02 MiB | 15662801 | 2943847 |

Source IDs i logiczne hashe wszystkich tabel są identyczne przy powtórzeniu:

- smoke: `source-sha256-a12866e1099c3ae2ae7c73cac5c533a35733618d85a3728cd5f0e1c7b527fc00`;
- temporal: `source-sha256-94829460645140b79a6f68e87194f74d2c8e55392e2702a9fecbe6b771116d22`.

`ai03-format-budget-1.0.0` pozostawia limit **300 s / 1024 MiB na profil**.
Data CI uruchamia ten sam target, ma timeout 30 minut i publikuje JUnit,
benchmark oraz skan Bandit. Przekroczenie limitu i niepowtarzalna identity
są blokujące; oba przypadki mają test negatywny. To lokalny odbiór:
Required CI tego brancha nie zostało jeszcze uruchomione zdalnie.

[Duży writer](writer-scale.json) zapisał **1460000 wierszy** w 542 plikach,
z pełnym odczytem kontrolnym: **211,61 s**, **76,58 MiB RSS**, 6899 rows/s,
205097930 B CSV i 8254062 B Parquet. Sort multiset i indeks dat są na dysku.
To benchmark fizycznego writera, nie profil ai-training ani kwalifikowany source.
Pomiary wykonywano współbieżnie na tej samej maszynie; wyniki nie służą
porównaniu sprzętu ani zastąpieniu pomiaru Linux CI.

## Kontrakt i kontrola zawartości

[Source manifest smoke](source-smoke.json) i [format manifest](format-smoke.json)
podają source ID/commit, requested/effective config, seed, watermarks/readiness,
typy, grain, klasy, counts/date ranges, physical checksums i logical hashes.
Writer code hash `59afea9c…`, dependency hash `820f9d97…`; pełne wartości są
w manifestach i pomiarach. Tabele i CSV pozostają poza Git.

Parquet zachowuje null/zero/closed, precyzję Decimal, business dates i UTC
availability oraz wszystkie append-only wersje ilości. Testy zmieniają
rozmiar porcji i próg partycjonowania; hashe logiczne nie zmieniają się.
Pozycje zamówień partycjonują się według źródłowej daty orders przez indeks
SQLite. Brak powiązania jest błędem, bez wymyślania daty.

Oddzielne facts/truth/operational_outputs/reports/manifests mają 40 tabel;
raw_events jest pustą przestrzenią dla przyszłego strumienia. Źródłowe
forecasts/anomalies nie stają się labelami ani cechami. Demo i wcześniejsze
archiwa zachowują CSV i dotychczasowe typy/identity.

Negatywne testy obejmują podmienione/missing/symlink CSV, błędne columns/ID,
niezgodną zawartość mimo zaktualizowanej checksumy, brak/duplikat tabeli,
niecałkowite/nonfinite wartości, null w wymaganym polu, utratę precyzji,
timestamp bez strefy/sub-microsecond, row/chunk bounds, utratę duplikatów,
root/path traversal/symlinki cleanup oraz tracked fixture ze znakami glob.

Generated exports są ignorowane przez Git. 12,8 MB dawnego small wyłączono
ze śledzenia; pliki lokalne zostały zachowane. Świeży checkout przygotowuje
brakujące CSV przed `api-seed-small`/`compose-seed`; kompletne CSV są nietknięte,
a częściowe źródło jest odrzucane. Sześć archiwów regresji ma łącznie
2435356 B po rozpakowaniu wobec 5 MiB limitu. Bieżącego fixture jest zero;
handoff fixture należy do 03.3. Cleanup chroni wszystkie śledzone pliki.

## Kolejny zakres

Można przejść do **03.2 — immutable exporter**. Format ma jawne
`snapshot_ready=false`: atomowa publikacja, allowlista faktów, przeliczenie
use-case gates, idempotencja/conflict oraz późniejszy importer/curated pozostają
do wykonania. 04 i 06 otworzy dopiero bramka cross-repo 03.6.
Generacja pełnych ai-dev/ai-training nadal materializuje tabele;
nie przyznano tym profilom odbioru end-to-end na podstawie writera.
