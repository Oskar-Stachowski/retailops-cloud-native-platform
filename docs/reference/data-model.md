# Model danych

[Dokumentacja](../README.md) · [Obsługa bazy](../guides/database.md) · [Dane syntetyczne](../guides/data.md)

PostgreSQL przechowuje dane aplikacji, historię workflow, odczyt strumieniowy
i metadane przebiegów modeli. Schemat definiują [migracje Alembic](../../services/api/alembic/versions/).
Modele [Pydantic](../../services/api/app/domain/models.py) walidują dane domenowe,
a [schematy API](../../services/api/app/api/schemas.py) opisują publiczne żądania
i odpowiedzi. SQLAlchemy Core służy migracjom; repozytoria wykonują zapytania
przez Psycopg.

## Tabele aplikacyjne

| Grupa | Tabele | Odpowiedzialność |
|---|---|---|
| Dane podstawowe | `products`, `users` | Produkty i użytkownicy będący wykonawcami/przypisanymi osobami w zapisach workflow |
| Sprzedaż i zapas | `sales`, `inventory_snapshots` | Sprzedaż produktu oraz stan w magazynie w określonym czasie |
| Sygnały | `forecasts`, `anomalies` | Prognoza dla okresu oraz odchylenie od oczekiwanej wartości |
| Decyzje | `alerts`, `recommendations` | Sygnały wymagające obsługi i proponowane działania |
| Historia | `workflow_actions`, `workflow_audit_log` | Akcje dotyczące alertów oraz wspólny zapis audytowy alertów i rekomendacji |
| Strumień | `realtime_event_log`, `live_metric_observations`, `realtime_consumer_state` | Status przetworzenia zdarzeń, obserwacje metryk i stan konsumenta |
| Przebiegi ML | `forecast_runs` | Identyfikacja modelu i danych, okna czasowe, metryki oraz referencje do artefaktów |

To 14 tabel aplikacyjnych. Alembic przechowuje numer zastosowanej migracji osobno
w `alembic_version`.

## Powiązania i odczyty

`products.id` łączy sprzedaż, zapasy, prognozy, anomalie, alerty i rekomendacje.
Alert może wskazywać anomalię i przypisanego użytkownika. Rekomendacja dotyczy
produktu i opcjonalnie odwołuje się do prognozy, anomalii lub alertu.
`workflow_actions.alert_id` wiąże akcję z alertem; `workflow_audit_log` identyfikuje
cel przez parę `entity_type` i `entity_id`.

Product 360 i dashboardy są agregatami odczytu tych danych. Ryzyko zapasu jest
wyliczane przez warstwę zapytań/usług; nie stanowi osobnej tabeli. Nazwa
magazynu w `inventory_snapshots` jest kodem tekstowym. Rozszerzone CSV generatora
mogą zawierać sklepy, zamówienia, pozycje zamówień, zwroty i promocje, ale nie
oznacza to istnienia odpowiadających im tabel w obecnej bazie API.

## Trwałość i integralność

Migracje definiują klucze obce, unikalność, ograniczenia dozwolonych wartości
i indeksy. Większość encji identyfikują UUID; stan konsumenta ma klucz
`consumer_name`. Kwoty i wartości prognoz używają typów `Numeric`, a znaczniki
czasu operacji typów ze strefą czasową. Szczegółowe typy i ograniczenia pozostają
w migracjach, aby uniknąć rozbieżnej kopii schematu w dokumentacji.

Klucz `forecast_runs.run_key` identyfikuje rekord aktualizowany przez powtórny
zapis metadanych. W `workflow_audit_log` unikalny częściowy indeks obejmuje
`entity_type`, `entity_id` i niepusty `idempotency_key`. Zapis stanu workflow
i jego historii odbywa się w jednej transakcji repozytorium.

Tożsamość wybrana w UI pochodzi z pamięci aplikacji, a nie z logowania do tabeli
`users`. Kod mapuje ją na użytkownika bazy dla historii akcji. Powiadomienia
demo i ich stan odczytania również nie mają tabeli.

## Ładowanie i rozwój schematu

[Seed](../../services/api/scripts/seed_demo_data.py) ładuje dziewięć podstawowych
tabel od `products` do `workflow_actions`, korzystając z CSV. Przed zapisem
wykonuje `TRUNCATE ... CASCADE`, co usuwa również zależną historię workflow.
Nie jest to przyrostowy import ani sposób zachowania danych użytkownika.

Tabele strumieniowe i `forecast_runs` są zasilane odrębnymi ścieżkami wykonania.
Nie należy traktować ponownego seedowania jako pełnego resetu wszystkich
14 tabel. Zmiany schematu dodawaj jako kolejne migracje; procedury znajdują się
w [przewodniku bazy](../guides/database.md).
