# PostgreSQL, migracje i dane początkowe

[Dokumentacja](../README.md) · [Uruchomienie lokalne](local-development.md) · [Model danych](../reference/data-model.md)

Compose używa PostgreSQL 16 i wykonuje kolejno `db` → `migrate` → `seed` → `api`.
Host bazy dla kontenerów to `db`; dla narzędzi uruchomionych na komputerze to
`localhost` i opublikowany port. Połączenie aplikacji określa `DATABASE_URL`.

## Wybór danych

Repozytorium zawiera dane `demo` i zapisany profil `small`. Na pierwszy start
wybierz mniejszy zestaw przez `RETAILOPS_SEED_DATA_PROFILE=demo` w lokalnej `.env`.
Domyślna konfiguracja używa `small`. Seed czyta istniejące CSV i nie uruchamia
generatora.

Aby odtworzyć profil na hoście:

```bash
make api-install
services/api/.venv/bin/python -m data.generator.main --profile small
```

Obsługiwane profile seedowania to `demo`, `small` i `medium`; `medium` trzeba
wygenerować przed użyciem. Własny katalog CSV można wskazać przez
`RETAILOPS_SEED_DATA_DIR`. W kontenerze musi to być ścieżka dostępna wewnątrz
kontenera, np. pod montowanym `/workspace/data`.

## Sprawdzenie działającej bazy

Poniższe polecenia używają danych logowania kontenera, więc nie zależą od
domyślnej nazwy użytkownika:

```bash
docker compose --profile dev exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose --profile dev exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT version();"'
docker compose --profile dev exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT version_num FROM alembic_version;"'
```

`/ready` sprawdza tylko możliwość wykonania `SELECT 1`. Sukces tego endpointu
nie potwierdza, że zastosowano migracje lub załadowano dane.

## Migracje

Przy pracy na hoście Make wczytuje `.env`, instaluje zależności i przekazuje
adres lokalnej bazy:

```bash
make db-up
make api-migrate
```

Druga komenda wykonuje `alembic upgrade head`. Sprawdzenie wersji w działającym
kontenerze API:

```bash
docker compose --profile dev exec -T api alembic current
docker compose --profile dev exec -T api alembic heads
```

Nową zmianę schematu zapisz w osobnej migracji. W środowisku deweloperskim,
z `DATABASE_URL` wskazującym właściwą bazę:

```bash
cd services/api
.venv/bin/alembic revision -m "describe_schema_change"
```

Uzupełnij `upgrade()` i `downgrade()` w nowym pliku. Projekt nie udostępnia
metadanych ORM do `--autogenerate` (`target_metadata = None`). Nie zmieniaj
migracji zastosowanej już do wspólnej bazy. Wycofanie obrazu aplikacji wymaga
zgodności ze schematem; nie uruchamia automatycznie `alembic downgrade`.

## Ponowne ładowanie danych

Seed jest operacją zastępującą dane: wykonuje `TRUNCATE ... RESTART IDENTITY
CASCADE`, a następnie ładuje dziewięć tabel CSV w jednej transakcji. Usuwa
dotychczasowe zmiany biznesowe i zależną historię workflow. Profile można
załadować poleceniami:

```bash
make api-seed-demo
make api-seed-small
make api-seed-medium
```

Wybierz jedno polecenie dla przygotowanego profilu, a nie wszystkie kolejno.
Każdy cel używa bazy wskazanej przez konfigurację Make. Tabele zdarzeń
i metadanych przebiegów modeli nie należą do tego importu, więc seed nie jest
pełnym resetem bazy.

`make api-integration-test` również wykonuje migracje i ładuje `demo` przed
testami. Nie kieruj go do bazy z danymi, które chcesz zachować.

## Zatrzymanie, backup i odtworzenie

Do zwykłego zatrzymania używaj procedury z
[przewodnika lokalnego](local-development.md#sprawdzenie-i-codzienna-obsługa).
`make compose-down` i `make db-down` zachowują wolumeny projektu. Następne
`make compose-up` uruchamia migracje, ale nie ładuje danych ponownie. Jedynie
jawne `make compose-seed` zastępuje tabele aplikacyjne, a `make compose-reset`
usuwa wszystkie nazwane wolumeny tego projektu. Procedura pierwszego startu
i resetu jest w [przewodniku lokalnym](local-development.md).

```bash
make db-backup
```

Backup w formacie `pg_dump --format=custom` i plik SHA-256 trafiają domyślnie
do `ci-cd/reports/db/backups/`. Odtworzenie zastępuje obiekty w bazie docelowej.
Przed użyciem zatrzymaj procesy zapisujące do wybranego celu i stosuj
[procedurę restore](../runbooks/db-restore.md) ze sprawdzeniem docelowej bazy
oraz sumy kontrolnej.

Do przećwiczenia odzyskania danych bez ingerencji w bazę developerską służy
`make db-recovery-drill`, tworzący odrębne środowisko. Kod operacji znajduje się
w [scripts/db](../../scripts/db/), a kontrakt schematu sprawdzają
[testy bazy](../../services/api/tests/test_database_schema.py).
