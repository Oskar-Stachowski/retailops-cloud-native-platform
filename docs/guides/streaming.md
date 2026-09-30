# Broker i przetwarzanie zdarzeń

Lokalny broker to Redpanda. Konfigurację zawierają
[`docker-compose.yml`](../../docker-compose.yml) i
[`k8s/overlays/dev/broker/`](../../k8s/overlays/dev/broker).
[Kontrakt zdarzeń](../reference/events.md) definiuje topic, typ i envelope.

## Compose

Najpierw uruchom aplikację zgodnie z [instrukcją lokalną](local-development.md).
Do niezależnego uruchomienia brokera i sprawdzenia topiców:

```bash
make broker-up
make broker-topics
```

Proces konsumenta ma własny entrypoint:

```bash
make api-install
make realtime-consumer
```

Wymaga istniejącej bazy po migracjach oraz właściwych `DATABASE_URL` i
`RETAILOPS_BROKER_BOOTSTRAP_SERVERS`. Dla klienta uruchamianego na hoście używaj
adresu publikowanego przez Compose; usługi w sieci kontenerowej używają
`redpanda:9092`. Bieżące wartości i porty sprawdzaj w Compose i Makefile.

## Replay i smoke

```bash
services/api/.venv/bin/python -m data.generator.realtime --profile demo
make streaming-smoke
```

Pierwsza komenda zapisuje `data/replay/demo/events.jsonl` oraz manifest.
Nie publikuje automatycznie pliku do brokera. Smoke sprawdza dostępne lokalne
elementy ścieżki streamingu; jego zakres wynika z
[`streaming_smoke.sh`](../../scripts/ci/streaming_smoke.sh).

```bash
make observability-demo-traffic
```

Ta komenda generuje aktywność demonstracyjną i zmienia dane w uruchomionej bazie.
Po jej wykonaniu sprawdź `/dashboard/live-operations`, `/metrics` i dashboard
streamingu w Grafanie. Używaj jej wyłącznie na danych demonstracyjnych.

Raporty robocze trafiają do `ci-cd/reports/`. Najnowsze zaakceptowane wyniki
prób lokalnych znajdują się w [dowodach](../evidence/README.md).

Awaria DB/handlera lub brak potwierdzonej kwarantanny zatrzymuje konsumenta
bez ACK. Po naprawie zależności uruchom go ponownie z tym samym group ID.
Błędny JSON lub schemat jest zachowany w PostgreSQL przed ACK.
[Runbook odtwarzania](../runbooks/realtime-recovery.md) opisuje inspekcję,
kontrolowaną poprawkę i replay bez usuwania oryginału.
