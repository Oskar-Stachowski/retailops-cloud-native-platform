# OPS-07 — kontrakt zdarzeń legacy v1

Odbiór lokalny: 2026-09-29. Bazą prac jest RetailOps `ac1c461ab80aae5a0154e17aab64e5fbe7d58154`.
Zakres: 13 legacy typów, pięć używanych tematów oraz osobny temat DLQ.

Kanoniczny [rejestr](../../../../services/api/app/contracts/retailops-realtime-events.v1.contract.json)
i [JSON Schema](../../../../services/api/app/contracts/realtime-events.v1.schema.json)
są pakowane z API. Starsza ścieżka `events/contracts/retailops-realtime-events.v1.contract.json`
jest odnośnikiem do tego samego rejestru. Generator i konsument odczytują jego
mapę `event_type → topic`. Test porównuje ją z domyślną subskrypcją, inicjalizacją
topiców w Compose i kind oraz kontrolą streamingu.

Konsument sprawdza wymagane pola, zadeklarowany i transportowy topic,
obsługiwaną wersję `1.0` oraz payload konkretnego typu. Schemat obejmuje także
obecny ruch demonstracyjny. Testy negatywne odrzucają brak lub zły topic,
przyszły major/minor, nieznany typ, pusty lub niekompletny payload, błędną
wartość liczbową i niezarejestrowane pole.

Generator nadaje stabilne ID dla ponowienia tej samej wersji zdarzenia;
zmieniona zawartość albo czas dostępności otrzymuje inny ID. Próba na dwóch
kontrastowych snapshotach nie znalazła wspólnego ID o różnej zawartości.
Historyczne znaczenie pól i routing legacy v1 pozostają zgodne z demo.

## Weryfikacja

- Pełny lokalny pytest `services/api/tests data/tests`: **1374 passed, 40 skipped**,
  Docker dostępny dla istniejących testów izolowanego workera.
- Końcowe testy kontraktu, konsumenta i runnera: **40 passed**.
- Walidacja danych/zdarzeń `scripts/data/validate_data_contracts.py`: **passed**.
- Ruff check API/data/ML i format check: **passed**; `git diff --check`: **passed**.
- Lokalny `docker build` API i uruchomienie pakietu: **passed**; obraz zawiera
  rejestr 13 typów i wszystkie 13 schematów payloadów.

## Granice

OPS-07 nie kwalifikuje trwałego ACK/DLQ; osobny bieżący odbiór tej granicy
opisuje [OPS-03](../03/README.md). `retailops.intelligence.v2`, zastępowanie wcześniejszego
wkładu faktu po natural key/version i przekazanie snapshot → replay należą do
etapu AI 10. Ze względu na zmianę sposobu wyznaczania ID ponowny import
historycznych zdarzeń do zachowanej projekcji wymaga resynchronizacji; opisuje
to [kontrakt i runbook](../../../reference/events.md).
