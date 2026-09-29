# AI 06.3 — deterministyczna polityka i realizacja dostaw

**Odbiór lokalny 29.09.2026 na branchu `ai/06-01-inventory-ledger`,
implementacja `a3ead60`.** Środowisko: macOS ARM64, Python 3.11.15
z `services/api/.venv`. [Rejestr](verification.json) zawiera commit,
checksums, komendy, konfigurację, przypadki CLI i wyniki.
[Kontrakt i uruchomienie](../../../../reference/reorder-policy.md) opisują
aktualne zachowanie. [Odrębny odbiór projekcji 06.5](../06.5/README.md)
wskazuje aktualny punkt wznowienia: **06.6 — integracja i publikacja danych**.

## Działające zachowanie

Polityka `periodic-review-stock-position-1.0.0` przegląda każdą fizyczną
pozycję według jawnego anchor/cadence. Stock position obejmuje dostępny zapas
oraz pozostałą znaną ilość zamówień. Target korzysta z safety/reorder floor,
sprzedaży znanej w pokrytym oknie i jawnego quoted lead time. MOQ rozlicza
jednocześnie ustawienie polityki oraz dostawcy, bez wymagania wielokrotności.
Konfiguracja ma własne known/available time i dokładnie pokrywa ledger scope.

Brak coverage, opening, znanej oferty lub konfiguracji pozostaje widoczny
i blokuje odbiór wymaganego review; nie jest zerem. Nieznane lub późniejsze
fakty nie uzupełniają wcześniejszego origin. Powtórny review po zapisaniu
order nie tworzy duplikatu. Partial receipt zmienia on-hand i outstanding,
zachowując ich wspólny stock position.

Osobny proces `supplier-fulfillment-two-point-1.0.0` używa jawnego seeda,
supplier truth i rozkładu bazowego mean ± std z rounding/clamping.
Reliability steruje disruption; wtedy przyjęcie jest opóźnione i częściowe.
Dokładne ułamki zachowują dodatnie ilości i ich konserwację, również przy jednej
sztuce. Losowania są keyed per order, bez zależności od współdzielonego RNG.
Pierwotny plan wynika z quote; przyszła realizacja nie staje się znanym ETA.

Fixture ma opening 8/0, sprzedaż 4, stan w origin 4/0 i pełną historię dwóch dni.
Target 9/8 prowadzi do order 5/8. Normal supply odbiera całość w dwóch receipts;
poor supply tworzy cztery częściowe/opóźnione receipts. Runner uzgadnia je
z kontraktem 06.2 i ledgerem, bez zmiany salda w origin.

## Weryfikacja

- **396 testów `data/tests`, zero błędów i pominięć**, w tym 72 nowe testy.
  Regresja zachowuje wcześniejsze ledger/supply, snapshot/export/handoff,
  Parquet i bramkę cross-repo.
- Nowe testy obejmują MOQ, cadence bez zaokrąglania czasu, ceiling target,
  pending/partial orders, idempotencję, zero demand, missing history/quote,
  unknown opening/config, unit/location/scope, UTC i ścisłe schematy.
  Późna sprzedaż/receipt i przyszły order nie zmieniają wcześniejszej decyzji.
  Zmiana seed/truth zmienia realizację przy niezmienionej decyzji operacyjnej.
- **17 rzeczywistych przypadków CLI** na commicie implementacji: pełny run
  i powtórzenie, normal/poor supply, inny seed, late sale, idempotent review,
  zero demand oraz wymagane `not_ready` i celowo błędne kontrakty.
  Exit 0/1 i status `passed`/`not_ready`/`failed` są zgodne z oczekiwaniem.
- Ruff check/format i mypy `--follow-imports=silent` przechodzą dla 13 plików
  pakietu inventory. Test jest sformatowany; trzy nowe JSON Schemas dokładnie
  odpowiadają modelom runtime.
- Oba standardowe smoke wykonano po dwa razy: oryginalne source IDs,
  46 hard gates na run i identyczne bajty CSV. Fingerprint generatora nie
  zmienił się względem main `68fe5d9`. Świeże demo zachowuje 17 CSV z baseline’u;
  19 śledzonych plików demo pozostaje bez zmian.

## Granice odbioru

To pojedynczy review i niezależne planowanie przyszłych receipts na oddzielnym
fixture. Chronologiczny wielodniowy symulator sprzedaży, shared stock,
fulfillment mapping, return eligibility i wytwarzanie coverage z przetworzonych
okien należą do 06.4. Coverage nie opisuje latent demand ani przyszłych korekt.

Supplier reliability oznacza brak disruption. Realizacja zawsze ostatecznie
dostarcza pełną ilość; permanent failure, cancellation oraz approval nie są
zaimplementowane. Clipping i zaokrąglenie zmieniają rozkład końcowego lead time.
Pełny raport zawiera rozdzieloną simulation truth i nie jest feature/API export.

Source 2.6 nie korzysta jeszcze z nowych modułów; `inventory_ready=false`.
DATA-06, snapshoty i pełne source/readiness gates pozostają otwarte.
Nie ma nowego source/curated ani nowych metryk modeli. Nie wykonano zdalnego
Required CI lub publikacji AI 06 na main.

Kod i testy są w commicie implementacji; osobny commit dokumentacji zawiera
ten odbiór. Pełne CLI/JUnit/compatibility reports pozostają pod ignorowanym
`ci-cd/reports/data/`; mały rejestr w Git zachowuje wyniki i checksums.
