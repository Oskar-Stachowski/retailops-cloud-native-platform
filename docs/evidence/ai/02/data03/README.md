# AI 02 / DATA-03 — chronologia i zwroty

Odbiór lokalny **2026-09-28**, branch `ai/02-data-03`, kod
`f30bb544825a444d043d2d325d05c5cbf5830386`, baza panelu/koszyków
`36dca1f48b475f1d77d2f01b95b257cf931c02f7`.
Zakres: chronologia i zwroty z punktu 5 etapu 02.
Bieżący odbiór źródła i workera: [DATA-05](../data05/README.md).
Kolejna instrukcja: [AI 03](../../../../plans/ai/etapy/03-snapshot-curated.md).

## Kontrakt i wynik

[Specyfikacja](../../../../reference/retail-returns.md) opisuje syntetyczną
politykę `retail-returns-1.0.0`, generator 0.6.0, source schema 2.4.0
oraz kanonizację 1.4.0. AI ma 37 CSV; legacy zachowuje 17.
Nowe return_policies, return_events i daily_return_cohorts mają schema,
klasy danych, grain, checksumy i zakresy czasowe w manifestach.

Zwrot wskazuje konkretną sale/order/item, fizyczną lokalizację i kanał.
Okno zależy od kategorii/kanału; returned_at jest liczone od sold_at,
bez przycinania do end_date. Częściowe zgłoszenia nie przekraczają
skumulowanej ilości zakupu. Refunded oddaje rzeczywiście zapłaconą cenę,
rejected ma refund 0. Statusy są terminalne; nie modelujemy korekt i retry
odrzuconej sztuki ani praw konsumenta.

Chronologia ordered ≤ sold ≤ returned, policy known-at oraz
returned ≤ ingested ≤ available są egzekwowane. Dostępność zwrotu
jest ograniczona do dwóch dni po zdarzeniu. History cutoff to północ UTC
po end_date. Return tail kończy się 39 dni później, po maksymalnym oknie
37 dni i dwóch dniach opóźnienia. Zwrot po discontinue rozlicza wcześniejszy
zakup; nie tworzy nowej aktywnej sprzedaży ani nie przedłuża panelu.

Net revenue to gross minus refundacje dostępne w konkretnym cutoffie.
Dzienne observations opisują wiedzę przy day close; późniejsze refundacje
nie przepisują ich ani targetu observed_sales_units. Osobne kohorty history
oraz return_tail pokazują późniejsze kwoty i dojrzałość każdego okna.
Brak zwrotu nie dowodzi mature zero, zanim nie minie window + opóźnienie.
Legacy returns.csv w AI zawiera tylko projekcję dostępną w history cutoffie.

## Wykonany odbiór

[acceptance.json](acceptance.json) pochodzi z czystego commita kodu.
Dwa ai-smoke i dwa ai-temporal-smoke mają identyczne source/feature IDs,
bajty CSV, raporty i watermarki. Kontrasty seed 42/43, 8/9 produktów i dat
zmieniają oba IDs. Osobny siedmiodniowy run DST ma wszystkie cztery kanały.
Każdy run zachowuje osiem bramek wymiarów, sześć cen, sześć panelu i 15
kontroli strukturalnych, a siedem bramek zwrotów przechodzi.

| Profil | Zdarzenia zwrotów | Dostępne w history | Późniejszy tail | Kohorty final | Refund history PLN | Refund final PLN |
|---|---:|---:|---:|---:|---:|---:|
| ai-smoke | 1044 | 591 | 453 | 1612 | 9855.06 | 18318.01 |
| ai-temporal-smoke | 1701 | 1499 | 202 | 2406 | 20603.13 | 23544.19 |

Wszystkie final kohorty są dojrzałe: 1612 ai-smoke i 2406 temporal.
Sztuki/gross sales są identyczne w obu cutoffach; net zmieniają wyłącznie
znane refundacje. Źródło nie traci późniejszych zdarzeń.
17 CSV demo i ograniczonego small są zgodne bajtowo z bazą DATA-01;
19 śledzonych plików demo nie zmieniono. Rzeczywiste archiwa source 2.0–2.3
zachowują source/feature IDs i parent. Archiwum 2.3 pochodzi z czystego
commita poprzedniego zakresu; [katalog fixtures](../../../../reference/source-compatibility-fixtures.md)
podaje pochodzenie i limit łącznego rozmiaru.

Sekwencyjny proces odbioru źródeł/cech i walidacji trwał **70,08 s**, peak RSS
**135,34 MiB** na macOS. Pełny pytest działał równolegle jako osobny proces;
to pomiar ograniczonego odbioru, bez izolowanego benchmarku ai-training i treningu.
Surowe CSV powstały wyłącznie w temp.

## Testy i kontrole

[verification.json](verification.json) zapisuje **621 testów**, bez failures/errors/skips,
w tym PostgreSQL/API i **36 testów DATA-03**. Coverage API z gałęziami wynosi
**83.82%**, przy wymaganych 70%. Testy obejmują sprzedaż przed zamówieniem,
zwrot przed sprzedażą, błędne referencje/polityki, pojedynczy i skumulowany
nadmiar zwrotu, kwoty/waluty, UTC, późną ingestię, fałszywy net/maturity,
wyciek i przycięcie tailu, brak kohorty, mikrosekundowe granice cutoff/deadline,
rejected refund, brak dojrzałego okna oraz odczyt rzeczywistego archiwum 2.3.
Przeliczenie hashów błędnego eksportu nie omija semantycznej bramki.

Ruff, format, skonfigurowane mypy i Bandit high/high przechodzą; staged diff
przechodzi Gitleaks. Cztery rzeczywiste komendy source/feature CLI kończą się 0,
uszkodzone pliki źródła/cech kończą się 1. Parent obu poprawnych eksportów jest zgodny.
Kontener PostgreSQL z nowymi migracjami i seedem demo został usunięty po testach.

## Odtworzenie

Polecenia z głównego katalogu repozytorium, z przygotowanym środowiskiem API:

```bash
services/api/.venv/bin/python -m scripts.data.verify_data03 \
  --output /tmp/retailops-data03-acceptance.json \
  --baseline docs/evidence/ai/02/data01/legacy-baseline.json --require-clean
PYTHONPATH=.:services/api services/api/.venv/bin/python -m pytest \
  services/api/tests/test_data_returns.py -q
```

Pełne polecenia DB/pytest i wynik kontroli znajdują się w
[verification.json](verification.json). Zdalnego Required CI i nowych modeli
nie uruchamiano. Source i features pozostają not_ready dla forecastingu,
anomaly, stockout i replay; inventory_ready=false. Returns-ready dotyczy
wyłącznie wersjonowanego komponentu zwrotów. Końcowy [odbiór source 2.6](../data05/README.md)
kwalifikuje rozpoczęcie AI 03; immutable import i curated pozostają kolejnym zakresem; zachowują
istniejącą historię wersji obserwacji i odczyt as-of.
