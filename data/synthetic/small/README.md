# RetailOps Synthetic Small Dataset

Ten katalog zawiera lokalnie wygenerowany profil `small`.

Katalog `data/synthetic/` jest ignorowany przez Git, wiec te pliki sa do
lokalnej analizy i testow, a nie do commita.

## Parametry Generacji

Komenda:

```bash
python3 -m data.generator.main --profile small
```

Domyslne parametry profilu:

- products: 100
- stores: 5
- warehouses: 3
- days: 90
- seed: 42
- format: CSV

## Wygenerowane Obszary Danych

| Plik | Rekordy danych | Znaczenie |
| --- | ---: | --- |
| `products.csv` | 100 | Katalog produktow i podstawowy wymiar biznesowy. |
| `users.csv` | 4 | Demo role operacyjne. |
| `stores.csv` | 5 | Punkty sprzedazy / lokacje sprzedazowe. |
| `warehouses.csv` | 3 | Magazyny uzywane przez inventory i stock movements. |
| `sales.csv` | 9000 | Dzienna sprzedaz produktow przez 90 dni. |
| `orders.csv` | 9000 | Zamowienia utworzone z referencji sprzedazy. |
| `order_items.csv` | 9000 | Pozycje zamowien powiazane z produktami. |
| `price_history.csv` | 300 | Trzy punkty cenowe na produkt. |
| `promotions.csv` | 100 | Jedna aktywna promocja na produkt. |
| `inventory_snapshots.csv` | 1300 | Tygodniowe snapshoty inventory. |
| `stock_movements.csv` | 10300 | Ruchy poczatkowego stanu i ruchy sprzedazowe. |
| `returns.csv` | 1800 | Zwroty wygenerowane z czesci order items. |
| `forecasts.csv` | 6 | Prognozy dla pierwszych produktow. |
| `anomalies.csv` | 20 | Syntetyczne anomalie operacyjne. |
| `alerts.csv` | 20 | Alerty utworzone z anomalii. |
| `recommendations.csv` | 20 | Rekomendacje powiazane z alertami/anomaliami. |
| `workflow_actions.csv` | 20 | Akcje workflow dla alertow. |

## Glowne Zaleznosci Biznesowe

### Product jako centrum modelu

`products.csv` jest glownym wymiarem biznesowym.

Zalezne pliki:

- `sales.product_id`
- `order_items.product_id`
- `price_history.product_id`
- `promotions.product_id`
- `inventory_snapshots.product_id`
- `stock_movements.product_id`
- `returns.product_id`
- `forecasts.product_id`
- `anomalies.product_id`
- `alerts.product_id`
- `recommendations.product_id`

Interpretacja:

Produkt laczy sprzedaz, ceny, promocje, inventory, anomalie, alerty i
rekomendacje. To pozwala budowac Product 360 i MLOps forecasting na poziomie
produktu.

### Store jako kontekst sprzedazy

`stores.csv` opisuje lokacje i kanaly sprzedazy.

Zalezne pliki:

- `orders.store_id`
- `orders.channel`
- `orders.region`
- `sales.channel`
- `sales.region`

Interpretacja:

Sprzedaz jest przypisana do regionu i kanalu. Zamowienie wskazuje konkretny
store, a `sales.csv` zachowuje uproszczony kontekst `channel + region`, zgodny z
obecnym MVP API.

### Warehouse jako kontekst inventory

`warehouses.csv` opisuje magazyny.

Zalezne pliki:

- `inventory_snapshots.warehouse_code`
- `stock_movements.warehouse_id`
- `stock_movements.warehouse_code`

Interpretacja:

Inventory snapshot pokazuje stan w magazynie w konkretnym czasie, a stock
movement pokazuje zdarzenia zmieniajace stan. To przygotowuje dane pod analize
stockout risk, overstock risk i supply chain operations.

### Sales -> Orders -> Order Items

`sales.csv` jest zachowany jako obecny prosty kontrakt API, ale profil `small`
dodaje bardziej realistyczny model zamowien.

Relacje:

```text
sales.order_reference
  -> orders.order_reference
orders.id
  -> order_items.order_id
order_items.product_id
  -> products.id
```

Interpretacja:

Kazdy rekord sprzedazy ma odpowiadajace zamowienie i jedna pozycje zamowienia.
To jest jeszcze uproszczenie, ale daje dobra baze pod przyszle koszyki z wieloma
produktami.

### Order Items -> Returns

`returns.csv` jest generowany z czesci `order_items.csv`.

Relacje:

```text
returns.order_id
  -> orders.id
returns.order_item_id
  -> order_items.id
returns.product_id
  -> products.id
```

Interpretacja:

Zwroty pomniejszaja efektywna sprzedaz i beda wazne dla net revenue, problemow
jakosciowych, forecastingu i analizy kategorii.

### Price History i Promotions

`price_history.csv` ma trzy punkty cenowe na produkt:

- previous
- current
- planned

`promotions.csv` ma jedna aktywna promocje na produkt.

Relacje:

```text
price_history.product_id
  -> products.id
promotions.product_id
  -> products.id
```

Interpretacja:

Te dane sa potrzebne do MLOps, bo cena i promocja sa kluczowymi feature'ami dla
popytu. Na razie promocje nie modyfikuja bezposrednio `sales.csv`; to powinno
wejsc w kolejnym etapie generatora.

### Inventory Snapshots -> Stock Movements

`inventory_snapshots.csv` daje tygodniowy obraz stanu magazynowego.

`stock_movements.csv` zawiera:

- `initial_stock` z inventory snapshots
- `sale` jako ujemny ruch magazynowy dla sprzedazy

Relacje:

```text
inventory_snapshots.product_id
  -> products.id
inventory_snapshots.warehouse_code
  -> warehouses.warehouse_code
stock_movements.product_id
  -> products.id
stock_movements.warehouse_id
  -> warehouses.id
```

Interpretacja:

Snapshot jest stanem w czasie, a movement jest zdarzeniem. Razem pozwalaja
budowac analize dostepnosci, rotacji zapasu i ryzyka brakow.

### Forecast -> Anomaly -> Alert -> Recommendation -> Workflow

Warstwa operacyjna zachowuje RetailOps flow.

Relacje:

```text
forecasts.product_id
  -> products.id
anomalies.product_id
  -> products.id
alerts.product_id
  -> products.id
alerts.anomaly_id
  -> anomalies.id
recommendations.alert_id
  -> alerts.id
recommendations.anomaly_id
  -> anomalies.id
workflow_actions.alert_id
  -> alerts.id
workflow_actions.performed_by_user_id
  -> users.id
```

Interpretacja:

To jest sciezka operacyjna: wykryty sygnal danych tworzy alert, alert dostaje
rekomendacje, a uzytkownik wykonuje akcje workflow.

## Jak Czytac Dataset

Najlepsza kolejnosc analizy:

1. `products.csv`
2. `stores.csv` i `warehouses.csv`
3. `sales.csv`, `orders.csv`, `order_items.csv`
4. `price_history.csv` i `promotions.csv`
5. `inventory_snapshots.csv` i `stock_movements.csv`
6. `returns.csv`
7. `forecasts.csv`, `anomalies.csv`, `alerts.csv`
8. `recommendations.csv`, `workflow_actions.csv`

## Ograniczenia Obecnego Profilu

- CSV jest wystarczajacy dla profilu `small`, ale `medium` i `large` powinny
  docelowo przejsc na Parquet/S3.
- Kazde zamowienie ma jedna pozycje. Wielopozycyjne koszyki powinny wejsc jako
  osobny etap.
- Promocje jeszcze nie wplywaja bezposrednio na popyt.
- Fulfillment jest uproszczony: ruchy sprzedazowe rotuja po magazynach.
- `small` nie jest seedowany do PostgreSQL; to synthetic data layer.
