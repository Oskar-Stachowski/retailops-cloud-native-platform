# AI 02 / DATA-04 — wspólne ceny i promocje

Odbiór lokalny **2026-09-28**, branch `ai/02-data-04`, kod
`5fedb2b2976ebfd60a53ac721b0e8194561ca9de`, baza DATA-02
`a4ddc79e6399c53a9538dd9bef96d0b8dfd58519`.
Zakres: cena i promocja, punkt 3 instrukcji etapu 02. Pozostały zakres opisuje
[aktualna instrukcja](../../../../plans/ai/etapy/02-dane-sprzedazowe.md).
Następne są popyt, pełny panel dzienny i koszyki (DATA-02/03/05).

## Zachowanie i kontrakty

Jeden resolver wybiera znane plany według produktu, scope, daty, wersji i ilości.
Ta sama wycena trafia do order item i sale, a sumy linii do zamówień i agregatów.
Brak znanej ceny, niejednoznaczny overlap lub priority oraz błędny rabat są błędami.
Późna rewizja nie zmienia wcześniejszej wiedzy; plan przyszłej ceny można odczytać
przed dniem docelowym, jeżeli był już dostępny. Pełna specyfikacja:
[ceny i promocje](../../../../reference/retail-pricing.md).

| Kontrakt | Obecne zachowanie |
|---|---|
| Generator / source schema | 0.4.0 / 2.2.0; 31 tabel AI, 17 tabel legacy. |
| Pricing | retail-pricing-1.0.0; price_plans, promotion_plans, sale_price_references, daily_price_observations i promotion_effect_truth. |
| Scope i czas | global/channel/location/location_channel; półotwarte okresy, known_at/available_at i cutoff zamówienia. |
| Promocje | percentage/bundle/clearance/seasonal i produkty bez promocji; exclusive_highest_priority. Bundle jest rabatem całej linii od dwóch sztuk, nie pakietem różnych SKU. |
| Truth | Pre przed startem, during w okresie kampanii, post po końcu; osobna tabela simulation_truth. Inne latent/noise/stockout fields wymagają dalszej separacji. |
| Obserwacje cen | Quantity-weighted realized price z availability; wynik transakcji, bez używania jako cecha target day. |
| Identity i cechy | Kanonizacja 1.2.0 i pricing policy w source ID; feature parent obejmuje pełne źródło. Feature schema 2.0 i kolumny pozostają bez zmian. |
| Odczyt historyczny | Rzeczywiste source 2.0 i 2.1 oraz ich feature sidecars zachowują IDs i parent. |
| Demo i legacy | CSV demo i ograniczonego small zgodne bajtowo z bazą; 19 śledzonych plików demo niezmienionych. |

## Wykonane próby

[acceptance.json](acceptance.json) zawiera dwa ai-smoke i dwa ai-temporal-smoke
z czystego kodu wskazanego powyżej. Powtórzenia dają te same source/feature IDs,
bajty CSV oraz raporty wymiarów i cen. Sześć bramek pricing, osiem bramek wymiarów
i istniejących 15 kontroli strukturalnych przechodzi. Oba profile sprawdzają też
znany przyszły plan i niezmienność wcześniejszej wyceny po dodaniu późnej rewizji.

| Profil | Nominalna siatka | Ważne dni asortymentu | Coverage cen | Sparse obserwacje cen / cechy |
|---|---:|---:|---:|---:|
| ai-smoke | 1 800 | 1 612 | 100% | 639 / 639 |
| ai-temporal-smoke | 2 448 | 2 406 | 100% | 852 / 852 |

Coverage cen obejmuje ważny asortyment i lifecycle, także dni zamknięcia.
Nie oznacza pokrycia pełnego panelu obserwacji sprzedaży.
Rzeczywiście zastosowane promocje występują we wszystkich czterech typach:

| Profil | Percentage | Bundle | Clearance | Seasonal | Produkty bez kampanii |
|---|---:|---:|---:|---:|---:|
| ai-smoke | 38 | 14 | 10 | 20 | 4 |
| ai-temporal-smoke | 6 | 9 | 4 | 9 | 1 |

Liczby typów oznaczają linie sprzedaży, nie liczbę kampanii. Sekwencyjny odbiór
trwał **8,01 s**, peak RSS **51,47 MiB**. To ograniczony pomiar generacji źródeł,
cech i walidacji na macOS, bez treningu i benchmarku pełnego ai-training.
Dane powstały w temp; raport nie zawiera dużych eksportów.

[verification.json](verification.json) zapisuje **543 testy**, 0 failures/errors/skips,
w tym PostgreSQL i API; coverage API **83,82%** przy progu 70%.
58 testów pricing sprawdza scope, wersje/cutoff, granice czasu, przyszłe plany,
cancellation, priority, ilości bundle i zaokrąglenia, pre/post oraz uzgodnienie
transakcji/agregatów. Brak ceny, overlap, błędny rabat, nieaktywna promocja,
niezgodne raporty i niewłaściwe timestampy są odrzucane. Przeliczenie checksum
błędnego eksportu nie omija kontroli semantycznej.

Ruff, format, skonfigurowane mypy (5 modułów API), Bandit high/high i Gitleaks
przechodzą. Cztery poprawne polecenia source/feature CLI kończą się 0;
uszkodzone CSV planów cen i cech kończą się 1. Migracje i świeży seed demo
wykonano na izolowanym PostgreSQL 16; tymczasowy kontener usunięto.
Zdalnego Required CI dla tego brancha nie uruchamiano.

## Odtworzenie

Z repo z przygotowanym środowiskiem API, na wskazanej rewizji:

```bash
services/api/.venv/bin/python -m scripts.data.verify_data04 \
  --output /tmp/retailops-data04-acceptance.json \
  --baseline docs/evidence/ai/02/data01/legacy-baseline.json --require-clean
PYTHONPATH=.:services/api services/api/.venv/bin/python -m pytest \
  services/api/tests/test_data_pricing.py -q
```

Pełne testy wymagają świeżej bazy z migracjami i seedem demo; polecenie i zakres
izolacji znajdują się w verification.json. Readiness forecasting, anomaly,
stockout i replay pozostaje not_ready, inventory_ready=false.
Popyt/panel/koszyki, chronologia/zwroty i pozostała separacja truth wymagają dalszej
pracy etapu 02 przed AI 03. Resolver jest dostępny dla przyszłych znanych
covariates; ten zakres nie dodaje planów cen/promocji do cech modelu.
