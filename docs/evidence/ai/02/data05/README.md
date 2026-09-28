# AI 02 / DATA-05 — odbiór źródła i izolacja workera

Odbiór lokalny **2026-09-28**, branch `ai/02-data-05`, kod
`6e06e909c7dac78675324e8d8ec42921e36b95e8`; implementacja separacji
`78f801f2e8bf33a92007821644ef9649b6c62bd5`, baza DATA-03
`0ab992cd69fec66c97a33f2535972f270975cb09`.
Zakres: końcowy odbiór źródła, punkt 6 etapu 02.
Następny zakres: [AI 03 — snapshot i curated](../../../../plans/ai/etapy/03-snapshot-curated.md).

## Kontrakt i granica procesu

[Specyfikacja](../../../../reference/source-acceptance.md) opisuje source **2.5.0**,
generator **0.7.0**, kanonizację **1.5.0** i 39 CSV AI. Produkty/sklepy mają
osobne tabele parametrów `retail-simulation-parameters-1.0.0`; sprzedaż AI
nie zawiera dawnych kolumn latent/noise/stockout/uplift. Truth i operational
outputs mają jawne klasy i nie są automatycznie feature inputs lub labelami.
Legacy zachowuje 17 CSV, wcześniejszy kontrakt seed/API i macierz cech 2.0.

Zaufany właściciel źródła waliduje manifest, dane i reports; admission sprawdza
również faktycznie projektowane rekordy względem checksumów/canonical hashes.
Podmiana pliku po pierwszym odczycie nie może otrzymać starego parent ID.
Oddzielny worker oblicza cechy 3.0 tylko z projekcji daily observations,
katalogu i kategorii. Nie generuje źródła ani nie dostaje jego katalogu.
Allowlista `forecast-facts-1.0.0` odrzuca dodatkowe pola i tabele w supervisorze
oraz we własnym runtime workera.

Runtime `facts-docker-runtime-1.0.0` używa Python 3.11.15 przypiętego digestem,
bez sieci, generatora, socketu Dockera, środowiska hosta i zapisów do root/code.
User 65534, cap-drop ALL, no-new-privileges, limity 256 MiB / 1 CPU / 64 procesy.
Jedyny mount zawiera sześć jawnych plików kodu; fakty i wyniki płyną przez stdio.
Brak Dockera lub obrazu kończy pracę błędem, bez fallbacku do procesu hosta.
Supervisor pozostaje właścicielem pełnego source i zapisu wyników; izolowany
jest proces obliczeń. To nie jest wdrożenie przyszłego serwisu modeli AI.

## Wykonany odbiór

[acceptance.json](acceptance.json) pochodzi z czystego commita kodu.
Dwa ai-smoke i dwa ai-temporal-smoke mają identyczne source/feature IDs,
bajty CSV, bramki, realizm i watermarki. Kontrasty seed 42/43, 8/9 produktów
i dat zmieniają oba IDs. Osobny run DST obejmuje wszystkie cztery kanały.
Każdy run przechodzi **45 hard checks**: 15 strukturalnych, osiem wymiarów,
sześć cen, sześć popytu, siedem zwrotów i trzy separacji/projekcji faktów.
Reader przelicza final source/quality/realism JSON i MD z rzeczywistych rekordów;
przeliczenie samych checksumów błędnego raportu nie omija bramki.

| Profil | Wiersze cech 3.0 | Hard checks | Średnia różnych pozycji koszyka | Zero-sales / otwarte dni |
|---|---:|---:|---:|---:|
| ai-smoke | 1612 | 45/45 | 1,8792 | 12,05% |
| ai-temporal-smoke | 2406 | 45/45 | 1,8049 | 13,09% |

Realism `observed-sales-realism-1.1.0` ma segmenty demand bucket/category/channel,
jawne mianowniki i minimalne sample sizes. Top 20% całego katalogu daje
48,80% / 67,31% revenue; oba katalogi mają mniej niż 50 produktów, więc status
jest **not_evaluable**, mimo policzonej wartości. Progi diagnostyczne 45–80%
i koszyki 1,2–3,5 wynikają z kontraktu, nie z dostosowania do final testu.
Segment poniżej 30 obserwacji nie otrzymuje passed. Closed nie jest zerem
w mianowniku otwartych dni. Refunded unit rate używa wyłącznie terminalnych
refundacji i dojrzałego ogona, bez przepisania historycznych labeli/net.
Causal promotion uplift i stockout mają null/not_ready.

Rzeczywisty worker przeszedł dziesięć prób: brak wskazanego katalogu source,
root source mount, host workspace, truth files, generatora, socketu, sieci,
host canary, uprawnień roota i prawa zapisu do kodu. Ominięcie walidacji
supervisora i podanie truth/inventory bezpośrednio do kontenera także kończy się
odrzuceniem. Trzy poprawne komendy source/features/identity mają exit 0;
uszkodzone bajty source i features — exit 1.

17 CSV demo i ograniczonego small są zgodne bajtowo z bazą DATA-01;
19 śledzonych plików demo pozostało identycznych. Rzeczywiste archiwa source
2.0–2.4 zachowują source/feature IDs i parent; razem mają 1,729,984 bajtów
po rozpakowaniu, poniżej 5 MiB. [Pochodzenie fixtures](../../../../reference/source-compatibility-fixtures.md).
Nowe surowe dane powstały tylko w temp.

Odbiór trwał **121,63 s**, peak RSS supervisora **139,44 MiB** na macOS ARM64.
Pełny pytest działał równolegle jako osobny proces. Nie zmierzono RSS kontenera;
256 MiB jest limitem workera. To ograniczony odbiór, bez benchmarku dużych
profili ani treningu. Indeks przypiętego obrazu zawiera Linux AMD64; lokalne
wykonanie było na ARM64, zdalnego CI tej rewizji nie uruchomiono.

## Testy i odtworzenie

[verification.json](verification.json) zapisuje **650 testów**, bez failures/errors/skips,
w tym **29 testów separacji i końcowych bramek**. Coverage API z gałęziami
wynosi **83,82%** przy wymaganych 70%. Pełny zestaw trwał 487,01 s.
Ruff/format (150 plików), skonfigurowane mypy (pięć modułów) i Bandit high/high
przechodzą; commity kodu i dokumentacja przechodzą Gitleaks. Świeży PostgreSQL otrzymał
migracje i seed demo; kontener został zatrzymany i usunięty po testach.
Testy obejmują pełne stare źródłowe bramki oraz truth/inventory/unknown fields,
parametry bez pokrycia/duplikaty, fałszywy readiness po rehash, błędny parent,
zmianę źródła w czasie admission, małe/zamknięte segmenty i realny proces Docker.

Polecenia odbioru z głównego katalogu, po przygotowaniu środowiska API i obrazu:

```bash
docker pull python@sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff
services/api/.venv/bin/python -m scripts.data.verify_data05 \
  --output /tmp/retailops-data05-acceptance.json \
  --baseline docs/evidence/ai/02/data01/legacy-baseline.json --require-clean
PYTHONPATH=.:services/api services/api/.venv/bin/python -m pytest \
  services/api/tests/test_source_isolation.py -q
```

Pełne polecenia DB/pytest znajdują się w verification.json. Runtime wymaga
lokalnego Dockera z przygotowanym obrazem; workflow API CI pobiera go jawnie.
Wynik daje **source_ready=true do AI 03** dla obserwowanej sprzedaży.
Forecasting/model serving, anomaly, stockout i replay pozostają not_ready;
inventory_ready=false. Typed Parquet, niezmienny snapshot, importer/curated
oraz wersje historycznych korekt ML-07 są kolejnym etapem. Nie wdrażano cloud
ani nie kwalifikowano dotychczasowego rejected RF do serving.
