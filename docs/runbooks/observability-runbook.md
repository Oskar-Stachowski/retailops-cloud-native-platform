# Diagnostyka monitoringu

Ścieżka sygnału: API `/metrics` → Prometheus → reguły → Grafana.
Konfiguracja: [instrukcja monitoringu](../guides/observability.md).

## Sprawdzenie działającego środowiska

```bash
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/metrics
curl --fail http://localhost:9090/-/ready
curl --fail 'http://localhost:9090/api/v1/targets?state=active'
curl --fail 'http://localhost:9090/api/v1/rules?type=alert'
curl --fail http://localhost:3001/api/health
make observability-smoke
```

Dostosuj adresy, jeśli porty w `.env` są inne. Obecność endpointu Prometheusa nie
wystarcza: target API musi być zdrowy i mieć zebrane próbki. Dla świeżego startu
poczekaj na scrape oraz pierwszą ewaluację reguł.

| Objaw | Diagnostyka |
|---|---|
| Target API `down` | Sprawdź gotowość API, `/metrics`, adres targetu w `observability/prometheus.yml` i połączenie w sieci Compose. |
| Grafana nie ma dashboardu | Sprawdź provisioning i pliki w `observability/grafana/`; przejrzyj logi Grafany. |
| Grafana działa, wykres pusty | Wykonaj zapytanie w Prometheusie, sprawdź źródło danych i zakres czasu panelu. |
| Metryki biznesowe są zerowe | Sprawdź tabele zdarzeń i konsumenta. Na danych demo można wykonać `make observability-demo-traffic`; zmienia to bazę. |
| Alert długo jest `pending` | Sprawdź rzeczywisty czas trwania warunku i `for` w regule. Nie skracaj progu, aby uzyskać wynik próby. |
| Alert `firing`, brak powiadomienia | Repozytorium nie konfiguruje Alertmanagera ani odbiorcy zewnętrznych powiadomień. |

```bash
docker compose --profile dev --profile observability logs --tail=100 api prometheus grafana
```

## Izolowana próba awarii

```bash
make compose-ci
```

Runner tworzy własne obrazy, porty loopback, bazę i wolumeny monitoringu. Zatrzymuje
wyłącznie swój kontener API, czeka na pending → firing z niezmienionym `for: 2m`,
przywraca API, sprawdza metryki/Grafanę i wygaśnięcie alertu. Usuwa swoje zasoby
na końcu, także po błędzie. Nie wykonuj ręcznej próby awarii na współdzielonej bazie.

Wyniki: `ci-cd/reports/observability/incident-drill.json` oraz
`ci-cd/reports/docker/isolated-runtime.json`. Ostatni utrwalony raport:
[monitoring](../evidence/observability/2026-09-26-validation.md).

Ta próba sprawdza działanie sygnału. [SLO scrape](../observability/slo.md)
nie jest SLO żądań użytkowników ani dowodem 30 dni dostępności.

## Zatrzymanie własnego środowiska

```bash
docker compose --profile dev --profile observability stop
```

`make observability-up` uruchamia także migracje i seed; nie jest neutralnym
restartem samego monitoringu. `make compose-down` usuwa wolumeny przez `-v`.
Pełny cykl start/stop opisuje [instrukcja lokalna](../guides/local-development.md).
