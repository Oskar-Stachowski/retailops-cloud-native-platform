# AI 06 — końcowy audyt i odbiór

Odbiór lokalny: 2026-09-29. **Cały zakres AI 06 jest wykonany.**
Runtime RetailOps: `f07ba22555a48b6c750f865f609e0893dfc129e0`; AI: `2574c06794b7b4f86393f23db1d9e97c16413706`.
[Weryfikacja](verification.json) wiąże rewizje, IDs, testy, wheel i zasoby.
[Runbook](../../../../reference/inventory-snapshots.md) opisuje domyślną ścieżkę.

## Wynik audytu

Nie ma otwartych blokad AI 06. Kontrola objęła ledger i pojedyncze opening,
wspólny zapas kanałów, historyczny routing, znaną politykę uzupełniania,
partial/delayed receipts, eligibility zwrotów, snapshot=known ledger,
kwalifikację lifecycle/coverage/maturity oraz separację truth.
36 bramek źródła jest ponownie liczonych po odczycie. Konsument niezależnie
uzgadnia ledger, sprzedaż/zwroty, orders/plans/receipts i known snapshots.
Audyt ujawnił brak kontroli osieroconego planu dostawy u konsumenta;
walidacja i test w pełni ponownie zapieczętowanych danych usuwają tę lukę.

Curated 1.1 zachowuje 43 tabele facts/plans, native grain i lineage kwalifikacji.
Sprzedaż czeka na causal availability, zwrot zachowuje magazyn oryginalnej sprzedaży,
a snapshot jest dostępny dopiero w swoim cutoff. Static records bez czasu pozostają
unknown. Odczyt as-of nie cofa przyszłych danych do wcześniejszego origin.
Testy wykrywają również podmianę tabeli po utworzeniu wielokrotnego czytnika.

## Weryfikacja

730 testów producenta i 784 testów AI przeszło bez błędów
ani pominięć. Dodatkowe 41 testów sprawdza końcowy dispatch CLI i starszy eksport.
Ruff/format oraz pełny mypy AI przechodzą; nowy moduł producenta i acceptance
przeszły ograniczony mypy z pominięciem importowanych modułów.
Szerszy mypy legacy generatora nadal zgłasza istniejące wcześniej błędy typów;
ten odbiór nie deklaruje pełnego type-check całego historycznego generatora.
Zachowano bajty 105 frozen plików producenta i 81 plików/kontraktów konsumenta.
Wheel poza checkoutem obsłużył publiczny i prywatny snapshot, budowę curated
oraz as-of wyłącznie na kontraktach dołączonych do pakietu.

| Profil i powtórzenie | Pełny czas [s] | Szczyt RSS [MiB] |
|---|---:|---:|
| ai-smoke-first | 83.44 | 218.36 |
| ai-smoke-repeat | 82.28 | 224.36 |
| ai-temporal-smoke-first | 178.64 | 292.97 |
| ai-temporal-smoke-repeat | 152.85 | 300.30 |

Każdy pomiar obejmuje świeży source → qualification → snapshot → import → curated
oraz niezależne porównania historycznych obserwacji i fizycznych stanów.
Limit: 300 s / 1024 MiB na przebieg, bez instalacji zależności.
Powtórzenia mają identyczne source/qualification/snapshot/curated IDs.
Idempotencja reimportu/rebuild, private opt-in i zgodność facts obu wariantów
mają osobne testy fixture; nie dodaje się prywatnych labeli do curated.
Profil smoke kwalifikuje 250 dodatnich/337 ujemnych okien, temporal 472/611.

## Readiness i granice

Odebrana ścieżka ma `source_ready=true` i `inventory_ready=true`; modele pozostają
nieodebrane. Curated zapisuje własne readiness. Frozen source 2.7 zachowuje
pierwotne flagi false i status `awaiting_ai03_handoff`; nie przepisujemy jego
manifestu ani historycznych IDs. Ten końcowy receipt i curated są dowodem odbioru
następnych warstw. AI 04/05 nie są zależnością ukończenia 06. Ich zgodna ocena
na nowych IDs i właściwy lifecycle są wymagane przed 07/08.

Domyślne CLI AI generuje 2.7 i eksportuje snapshot 1.1. `--source-version 2.6`
odtwarza jawny wariant zgodności. Demo/API/seeder i historyczne funkcje generatora
zachowują dotychczasowy kontrakt. Smoke nie jest odbiorem dev/training ani modeli.

## Publikacja

Pełny pipeline AI 06 jest obowiązkowym jobem Data CI, z przypiętym konsumentem.
Publikacja na chroniony main przechodzi Required CI PR i następnie Required CI push.
Stan zdalnego odbioru: [RetailOps](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/workflows/required-ci.yml),
[AI](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/actions/workflows/required-ci.yml).
