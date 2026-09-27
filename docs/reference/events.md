# Kontrakt zdarzeń

Poniżej opisano aktualny kontrakt wykonywany przez
[konsumenta](../../services/api/app/services/realtime_consumer.py).
Wymagane pola envelope: `event_id`, `event_type`, `schema_version`,
`source`, `correlation_id`, `occurred_at`, `ingested_at`, `payload`.

`event_id` jest kluczem deduplikacji. `occurred_at` opisuje czas zdarzenia,
`ingested_at` czas przyjęcia; kolejność dostarczenia nie musi odpowiadać czasowi
zdarzenia. Walidator i konsument definiują faktycznie obsługiwane payloady.

| Topic | Zdarzenia |
|---|---|
| `retailops.sales.v1` | `order_created`, `sale_completed`, `return_completed` |
| `retailops.inventory.v1` | `stock_changed`, `inventory_snapshot_recorded`, `replenishment_completed` |
| `retailops.pricing.v1` | `price_changed`, `promotion_started`, `promotion_ended` |
| `retailops.intelligence.v1` | `forecast_generated`, `anomaly_detected` |
| `retailops.operations.v1` | `alert_created`, `workflow_action_performed` |

Broker tworzy także `retailops.dlq.v1`. Plik
[`retailops-realtime-events.v1.contract.json`](../../events/contracts/retailops-realtime-events.v1.contract.json)
nie jest jeszcze zgodny z tym zestawem: wymienia odrębne topiki orders/ml,
pomija zwroty i replenishment oraz wymaga pola `topic`. To otwarta rozbieżność
kontraktu, nie alternatywna instrukcja konfiguracji brokera.

## Implementacja

- [Generator replay JSONL](../../data/generator/realtime.py) tworzy zdarzenia i manifest na podstawie profilu danych.
- [Konsument](../../services/api/app/services/realtime_consumer.py) waliduje zdarzenia, deduplikuje i aktualizuje model odczytu.
- [Proces brokera](../../services/api/scripts/run_realtime_consumer.py) pobiera komunikaty z Redpandy.
- PostgreSQL przechowuje `realtime_event_log`, `live_metric_observations` i `realtime_consumer_state`; szczegóły w [opisie trwałości](live-metrics-persistence.md).

Przetwarzanie lokalne i test deduplikacji nie dowodzą dokładnie jednokrotnego
dostarczenia w całym systemie. Aktualny problem potwierdzania offsetu po błędzie
jest opisany w [audycie](../audits/open-findings.md).

Uruchamianie brokera i sprawdzanie metryk: [instrukcja streamingu](../guides/streaming.md).
