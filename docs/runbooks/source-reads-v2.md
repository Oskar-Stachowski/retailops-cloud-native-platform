# AI 10 — chroniony, ograniczony odczyt źródła v2

Status: przyrost integracji REST; cały AI 10 pozostaje `in_progress`.
Endpointy `/integration/v2/products`, `/sales`, `/inventory-snapshots`,
`/forecasts`, `/inventory-risks` (każdy pod prefiksem `/integration/v2`)
zachowują istniejące modele odpowiedzi i nazwy filtrów. Wymagają jednego
`product_id`; sales wymaga także `channel` i obu timestampów okresu,
inventory wymaga `warehouse_code` i obu timestampów, forecasts obu dat.
Default limit 50, max 100, offset 0..10000, okres do 90 dni. Unknown i
powtórzone parametry nie są ignorowane. Sortowanie jest allowlistowane.

To **bounded live reads**, nie pełny eksport. Każda strona i jej count
pochodzą z jednej read-only repeatable-read transakcji z timeoutem 3 s.
Kolejne żądania nie mają wspólnego snapshotu. `total` może zmienić się między
stronami; nie służy do budowania snapshot/replay manifestu. Forecast ma
dodatkowy stabilny tie-breaker `id`, bez zmiany wartości lub modeli.

## Tożsamość i granty

Ustaw `RETAILOPS_SOURCE_ACCESS_POLICY` na prywatny, zwykły plik właściciela,
z prawami `0600`, poza Git, do 64 KiB. Schema:

```json
{
  "version": "retailops-source-access-1.0",
  "principals": [{
    "principal_id": "ai-source-pipeline",
    "credential_sha256": "SHA256_PRYWATNEGO_TOKENU",
    "resources": ["products", "sales", "inventory-snapshots"],
    "product_ids": ["UUID_PRODUKTU"],
    "channels": ["store"],
    "warehouse_codes": ["WH-01"]
  }]
}
```

Token Bearer ma 32..256 znaków; serwer porównuje hash w stałym czasie.
Grant zawiera do 20 produktów, 5 magazynów i jawne zasoby. Obcy produkt,
kanał, magazyn lub zasób daje 403 przed DB. Brak/niepoprawny token daje 401;
uszkodzony prywatny plik lub DB outage daje bezpieczne 503. Policy jest
cache'owana: po zmianie/revocation zrestartuj wyłącznie własne API.
`forecasts` i `inventory-risks` wymagają oddzielnego nadania zasobu, bo
dotyczą całego produktu; nie są ograniczone do przyznanego kanału/magazynu.
Nie dziedziczą praw demo `user_id`, operatora ani ML read credential.
Legacy endpointy pozostają dotychczasowym interfejsem demo; nie należy
udostępniać ich jako zabezpieczonej ścieżki usługowej. Deployment musi
ograniczyć publiczny ingress do zatwierdzonej powierzchni API.

## Kontrakt i brak wsparcia

`GET /integration/v2/capabilities` jest również uwierzytelniony. Deklaruje:

- brak pełnego sales grain: brak `store_id`, `order_id`, `ingested_at`,
  wersji rekordu; `created_at` nie dowodzi dostępności historycznej;
- brak wersjonowanego warehouse→selling-location mapping;
- legacy forecast to produkt/okres/ilość; legacy risk to heurystyka,
  nie probability modelu AI 08;
- brak immutable REST snapshot i przekazania offsetów do replay.

`GET /integration/v2/snapshot` zwraca jawne 409
`source_snapshot_unsupported`. Działający import plikowy AI 03 pozostaje
ścieżką historycznego snapshotu. Nie wymyślać brakujących pól lub offsetów.
Odczyt HTTP nie nadaje świeżości `current`: potrzebny jest właściwy watermark
kompletności, pochodzenie i availability. `X-RetailOps-Read-Mode`,
`X-RetailOps-Snapshot-Supported`, `X-RetailOps-Source-Contract-Sha256` oraz
`Cache-Control: no-store` opisują ograniczenia i pin odpowiedzi.

Wygenerowany kontrakt jest w
`services/api/app/contracts/source-reads-v2/openapi.json`. Regeneracja:

```sh
PYTHONPATH=services/api services/api/.venv/bin/python \
  services/api/scripts/export_source_read_contract.py
PYTHONPATH=services/api services/api/.venv/bin/python \
  services/api/scripts/export_source_read_contract.py --check
```

Required CI sprawdza drift rzeczywistych parametrów i response schemas.
Testy endpointów sprawdzają auth/scope, limity, daty, unsupported snapshot
i bezpieczny DB outage. Required API CI pobiera dokładny klient AI z
`source-reads-v2/client.json` i wymaga rzeczywistego testu HTTP/PostgreSQL.
Test wykonuje pięć odczytów, strony 100+25 sales rows, no-data i błędne granty,
zachowuje jednostki/legacy semantykę; nie kwalifikuje ML. Local invocation:

```sh
PYTHONPATH=services/api:. REQUIRE_SOURCE_REST_TESTS=1 \
  RETAILOPS_AI_SOURCE_CLIENT_ROOT=/path/to/pinned-ai \
  services/api/.venv/bin/python -m pytest \
  services/api/tests/test_source_read_cross_repo.py
```

Baza musi być jednorazową usługą GitHub CI albo własną
`retailops_ai10_rest_*` na loopback. Test tworzy i usuwa tylko rekordy jednego
własnego UUID produktu. Brak klienta lub DB nie jest zaliczanym skip w CI.

Rollback: zatrzymaj/wyłącz własnego klienta, usuń grant usługi i zrestartuj
własne API. Nie ma nowej migracji ani cleanup wspólnej bazy/brokera.
