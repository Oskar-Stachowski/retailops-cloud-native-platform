# Kontrakt zdarzeń

Kanoniczny [rejestr legacy v1](../../services/api/app/contracts/retailops-realtime-events.v1.contract.json)
i [wykonywalny JSON Schema](../../services/api/app/contracts/realtime-events.v1.schema.json)
są dołączone do obrazu API. Dotychczasowa ścieżka
`events/contracts/retailops-realtime-events.v1.contract.json` wskazuje ten sam plik.
Konsument wymaga `event_id`, `event_type`, `topic`, `schema_version`, `source`,
`correlation_id`, `occurred_at`, `ingested_at` i `payload`.
Obsługiwana wersja to dokładnie `1.0`; inny major lub niezatwierdzony minor jest
odrzucany. Schemat ma osobny payload dla każdego z 13 typów i odrzuca nieznane pola.

`event_id` jest UUID i kluczem deduplikacji zgodnym z typem kolumny PostgreSQL.
Generator wyznacza go z seed, source,
typu, naturalnego klucza i skrótu kanonicznej wersji payloadu oraz czasów.
Powtórzenie tej samej wersji ma ten sam ID; zmieniona zawartość albo availability
otrzymuje nowy ID. Zewnętrzni producenci podają własny ID zgodny z kontraktem.
Rozliczenie różnych wersji tego samego faktu biznesowego w projekcji pozostaje
zakresem etapu 10; samo nowe ID nie zastępuje wcześniejszego wkładu w metrykach.
Po zmianie algorytmu ID nie wgrywaj tego samego historycznego replay do starego
`realtime_event_log` bez resynchronizacji projekcji: nowe ID mogłyby doliczyć
te same fakty ponownie. Migracja istniejącego stanu należy do procedury
snapshot/replay w etapie 10.
`occurred_at` opisuje czas zdarzenia,
`ingested_at` czas przyjęcia; kolejność dostarczenia nie musi odpowiadać czasowi
zdarzenia. Konsument porównuje `topic` z typem zdarzenia oraz tematem transportu.

| Topic | Zdarzenia |
|---|---|
| `retailops.sales.v1` | `order_created`, `sale_completed`, `return_completed` |
| `retailops.inventory.v1` | `stock_changed`, `inventory_snapshot_recorded`, `replenishment_completed` |
| `retailops.pricing.v1` | `price_changed`, `promotion_started`, `promotion_ended` |
| `retailops.intelligence.v1` | `forecast_generated`, `anomaly_detected` |
| `retailops.operations.v1` | `alert_created`, `workflow_action_performed` |

Broker tworzy także `retailops.dlq.v1`. Tematy `retailops.orders.v1` i
`retailops.ml.v1` nie są częścią używanego legacy v1. Bogate wyniki AI będą
miały oddzielny `retailops.intelligence.v2` w etapie 10.

## Implementacja

- [Generator replay JSONL](../../data/generator/realtime.py) tworzy zdarzenia i manifest na podstawie profilu danych.
- [Konsument](../../services/api/app/services/realtime_consumer.py) waliduje zdarzenia, deduplikuje i aktualizuje model odczytu.
- [Proces brokera](../../services/api/scripts/run_realtime_consumer.py) pobiera komunikaty z Redpandy.
- PostgreSQL przechowuje `realtime_event_log`, `live_metric_observations` i `realtime_consumer_state`; szczegóły w [opisie trwałości](live-metrics-persistence.md).

Runner zatwierdza offset synchronicznie po trwałej transakcji metryk i statusu
albo po zachowaniu surowej wiadomości w kwarantannie PostgreSQL. Awaria DB,
handlera, kwarantanny lub ACK zatrzymuje proces przed pobraniem kolejnego komunikatu.
Replay po zapisie i przed ACK korzysta z deduplikacji po UUID.
Source `retailops.consumer.quarantine` jest zarezerwowany dla wpisów transportowych.
[Procedura awarii i odtwarzania](../runbooks/realtime-recovery.md) opisuje
zachowane bajty, kontrolowany replay i ograniczenia. To dostarczanie co najmniej
raz z idempotentną projekcją metryk; wyniki AI v2 i projekcje domenowe mają
osobny odbiór w etapie 10.

Uruchamianie brokera i sprawdzanie metryk: [instrukcja streamingu](../guides/streaming.md).
