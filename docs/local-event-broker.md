# RetailOps Local Event Broker

## 1. Purpose

Sprint 9 adds a local Kafka-compatible broker to the Docker Compose runtime.
The broker is used for real-time retail event replay and later API consumer
work.

The local broker is Redpanda. It keeps local development simple while matching
Kafka client semantics closely enough for a future Amazon MSK mapping.

## 2. Services

Docker Compose services:

| Service | Purpose |
| --- | --- |
| `redpanda` | Single-node Kafka-compatible broker for local development. |
| `redpanda-init` | One-shot topic initialization service. |

Local host ports:

| Variable | Default | Purpose |
| --- | ---: | --- |
| `REDPANDA_KAFKA_PORT` | `19092` | Kafka API exposed to host tools. |
| `REDPANDA_ADMIN_PORT` | `19644` | Redpanda Admin API exposed to host tools. |

Internal Compose address:

```text
redpanda:9092
```

Host-side address:

```text
localhost:19092
```

## 3. Topics

The init service creates the Sprint 9 topics from the event contracts:

| Topic | Purpose |
| --- | --- |
| `retailops.sales.v1` | Orders, sales and returns. |
| `retailops.inventory.v1` | Stock movements, snapshots and replenishment. |
| `retailops.pricing.v1` | Price and promotion changes. |
| `retailops.intelligence.v1` | Forecasts and anomalies. |
| `retailops.operations.v1` | Alerts and workflow actions. |
| `retailops.dlq.v1` | Dead-letter events. |

Each topic starts with:

```text
partitions: 3
replicas: 1
```

This is intentionally local-only. Production-like replication belongs to a
future multi-broker or managed-cloud setup.

## 4. Commands

Start only the broker and topics:

```bash
make broker-up
```

List topics:

```bash
make broker-topics
```

Start the full local stack:

```bash
make compose-up
```

Validate Compose config:

```bash
make compose-config
```

Stop and remove local state:

```bash
make compose-down
```

## 5. Runtime Notes

The API service receives:

```text
RETAILOPS_BROKER_BOOTSTRAP_SERVERS=redpanda:9092
```

The API consumer skeleton lives in
[`services/api/app/services/realtime_consumer.py`](../services/api/app/services/realtime_consumer.py)
and is attached to `app.state` during application startup. It validates event
envelopes and dispatches events to placeholder handlers, but it does not yet
connect to the broker.

Host tools should use:

```text
RETAILOPS_BROKER_BOOTSTRAP_SERVERS=localhost:19092
```

## 6. AWS Mapping

| Local capability | AWS direction |
| --- | --- |
| Redpanda single-node broker | Amazon MSK or another Kafka-compatible service. |
| Local topics | MSK topics. |
| DLQ topic | SQS DLQ or Kafka DLQ topic depending on final architecture. |
| Admin/health checks | CloudWatch, Managed Prometheus and broker metrics. |

EventBridge remains a good future option for selected integration events, but
the local Sprint 9 implementation starts with Kafka-compatible streaming.
