# Audyt AI 02 i gotowość do AI 03

**Decyzja: można rozpocząć lokalną realizację AI 03**, zaczynając od typed
Parquet i polityki artefaktów. Źródło jest zakwalifikowane do pierwszego
snapshotu syntetycznej sprzedaży `observed_sales_units`. Nie znaleziono
blokera rozpoczęcia tego zakresu. Przed pierwszą publikacją niezmiennego
snapshotu trzeba zamknąć DATA-07 opisane poniżej.

Audyt: **28.09.2026**, branch `ai/02-data-05`, HEAD
`a82152af93ed60f3879d923a3006478fb115930e`, implementacja
`6e06e909c7dac78675324e8d8ec42921e36b95e8`.
[Wynik maszynowy](verification.json) zawiera komendy, konfiguracje, IDs, hashe,
wyniki i zakres prób. Przegląd objął pierwotny pełny plan etapu 02 z `e665935`,
obecne kontrakty, kod generatora i workera, evidence komponentów oraz
[warunki wejścia AI 03](../../../../plans/ai/etapy/03-snapshot-curated.md).

## Pokrycie zakresów AI 02

| Zakres | Wynik i granica dowodu |
|---|---|
| DATA-01: konfiguracja i identity | Jawne daty i efektywne parametry; powtarzalne source/feature IDs i bajty. Seed, rozmiar i data zmieniają IDs. Odczyt archiwów 2.0–2.4 zachowuje ich tożsamość. Luka pełnego fingerprintu kodu: DATA-07. |
| DATA-02: wymiary i kalendarz | SKU, lifecycle, aktywne kombinacje, oddzielne lokalizacje/kanały, routing i kalendarz PL/DE z testami DST oraz granic dostępności. |
| DATA-04: ceny i promocje | Coverage ważnych kombinacji, wersje znane w origin, scope i konflikt planów, wspólna cena transakcyjna oraz poprawny kierunek pre/post. |
| Popyt, panel i koszyki | Pełna ważna siatka; jawne zero/closed/missing, jednokrotne demand weight, konserwacja sztuk/przychodu i koszyki bez powtórzeń. Brak lub późna dostępność nie stają się zerem. |
| DATA-03: chronologia i zwroty | Order → sale → return, konkretne pozycje i ilości, refundacja zapłaconej ceny, cutoffy i 39-dniowy ogon. Ledger inventory pozostaje AI 06. |
| DATA-05: separacja i bramki | 45 hard gates, raporty przeliczane z danych, osobne parametry symulacji i rzeczywisty worker przyjmujący trzy projekcje faktów. Realism ma jawne segmenty, mianowniki i niewystarczające próby. |

**Ograniczenie pierwotnego wymagania PIT:** testy planów cenowych i późniejszych
zwrotów przechodzą, ale pełna niezmienność agregatów po zewnętrznej late correction
nie jest ukończona. `daily_demand_observations` zachowuje jeden agregat z maksymalną
dostępnością, nie wcześniejsze wersje. Jest to otwarte ML-07, wymagane w importerze,
curated i odczycie as-of w AI 03–04. Dopuszczony obecny generator dostarcza sprzedaż
tego samego dnia; ta decyzja nie kwalifikuje pełnego replay zewnętrznej historii.
Odbiór AI 02 dotyczy wskazanego ograniczonego źródła, nie wszystkich przyszłych
gwarancji kontraktu danych i czasu.

## Wykonane sprawdzenia

Ponownie uruchomiono `scripts.data.verify_data05 --require-clean` na bieżącym
kodzie: dwa pełne `ai-smoke`, dwa `ai-temporal-smoke`, cztery kontrasty seed/rozmiar/
data oraz osobny profil DST ze wszystkimi kanałami. Każdy z dziewięciu przebiegów
przeszedł **45/45 hard gates**.

| Profil podstawowy | Wiersze cech | Powtórzenie danych/IDs | Bramki |
|---|---:|---|---:|
| ai-smoke | 1612 | zgodne | 45/45 |
| ai-temporal-smoke | 2406 | zgodne | 45/45 |

Wszystkie wartości semantyczne nowego raportu są identyczne z
[odbiorem DATA-05](../data05/acceptance.json), w tym artefakty, hashe, raporty,
readiness i watermarki. Różnią się wyłącznie pomiary czasu/RSS, katalogi
tymczasowe poleceń i commit provenance po zmianie dokumentacji.
Zachowano 17 CSV demo, 17 CSV small i 19 śledzonych plików demo.

Dziesięć prób izolacji kontenera przeszło; dodatkowe truth i inventory odrzucił
sam worker po pominięciu walidacji supervisora. Poprawne komendy verify/generate
zwróciły 0, uszkodzone bajty source/features — 1. Próba nie daje workerowi source,
repo, generatora, socketu, sieci ani zmiennych hosta. Supervisor pozostaje
zaufanym właścicielem źródła.

**206 świeżych testów przeszło**, bez failures/errors/skips:

- 36 testów granic czasu, semantyki popytu, cen i zwrotów;
- 98 testów negatywnych bramek wymiarów, cen, panelu i zwrotów;
- 72 testy identity i izolacji, w tym rzeczywisty Docker.

Pierwszą próbę testów izolacji ograniczył sandboxowy brak dostępu do socketu
Dockera; pełne ponowienie z dostępem do Dockera przeszło. Odbiór źródła trwał
150,433 s, peak RSS supervisora 139 804 672 B. Pomiary wykonywano równolegle
z innymi testami; to odbiór ograniczony, nie benchmark budżetu CI ani dużych profili.
RSS kontenera nie był mierzony; worker ma limit 256 MiB.

Niezależnie sprawdzono surowy JUnit i coverage wcześniejszego pełnego odbioru:
**650 testów bez pominięć, coverage API 83,82%**. Ich SHA oraz aktualne fingerprinty
source/feature/dependencies odpowiadają [zapisanemu receipt](../data05/verification.json).
Nie uruchamiano ponownie całego zestawu ani bazy; nie przedstawiamy tych 650 testów
jako nowego przebiegu audytu. Nowe testy są częściowo podzbiorem tego zestawu.

## Otwarte ustalenie DATA-07

Fingerprint cech pomija `ml/__init__.py` i `ml/features/__init__.py`, mimo że
worker je wykonuje. [Reprodukcja](worker-provenance-probe.py) w kopii tymczasowej
dodaje wykonywany znacznik do inicjalizatora; fingerprint i feature ID przy tych
samych wierszach nie zmieniają się. Jest to luka provenance kodu, nie kolizja
hashów różnych danych. Obecne pliki zawierają wyłącznie docstringi, więc wynik
nie podważa bieżących danych ani granicy izolacji.

Priorytet **P2 — odtwarzalność**, bez blokady rozpoczęcia AI 03. Przed pierwszą
publikacją snapshotu objąć fingerprintem wszystkie wykonywane pliki, sprawdzić
zmianę code hash/ID oraz wykrywanie modified code, zachowując odczyt dawnych IDs.
Aktualne kryterium zamknięcia: [otwarte ustalenia](../../../../audits/open-findings.md).

Reprodukcja z katalogu głównego repo:

```sh
env PYTHONPATH=services/api:. services/api/.venv/bin/python docs/evidence/ai/02/audit/worker-provenance-probe.py
```

## Warunki dalszej pracy

- **AI 03 można rozpocząć:** Parquet, polityka plików, pełny fingerprint i immutable
  exporter w RetailOps; następnie kontrakt, importer i curated w repo AI.
- ML-07 wymaga wersji korekt/as-of przed odbiorem historii i pełnym replay.
  DATA-06 nie blokuje forecast-only; `inventory_ready=false` pozostaje obowiązujące.
- Forecasting, anomaly, stockout i replay pozostają `not_ready`. Modele, serving,
  duże profile i pełna integracja nie były przedmiotem tego odbioru.
- Brak nowego dowodu zdalnego Required CI dla zmian etapu 02. Przed merge do
  chronionego `main` potrzebny jest zielony wynik. Lokalny worker był sprawdzony
  na Linux ARM64 przez Docker Desktop; ten audyt nie wykonał próby Linux AMD64.
- AI 04 i AI 06 otworzyć dopiero po bramce generator → export → import → curated,
  dwukrotnie na obu profilach smoke, zgodnie z kryteriami końca AI 03.

Otwarte problemy transportu i kontraktów zdarzeń OPS-03/07 należą do integracji
AI 10, a pozostałe ruchome obrazy/actions OPS-06 do odbioru wydań. Pierwszy import
plikowy nie wymaga działającego brokera ani operacyjnej bazy RetailOps.
