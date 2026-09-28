# Uruchomienie lokalne

[Dokumentacja](../README.md) · [Architektura](../architecture/overview.md) · [Testowanie](testing.md)

Wszystkie polecenia wykonuj z katalogu głównego repozytorium, chyba że blok
zawiera `cd`. Do uruchomienia kontenerów potrzebujesz Git, Docker i wtyczki
Docker Compose. Make upraszcza polecenia; Python i Node są potrzebne dopiero do
pracy poza kontenerami oraz części narzędzi testowych.

## Pierwsze uruchomienie

Utwórz lokalną konfigurację, jeśli `.env` jeszcze nie istnieje:

```bash
cp .env.example .env
```

Compose przypina wszystkie publikowane porty do `127.0.0.1`; zmiana
`HOST_BIND` w `.env` nie wystawia ich na inne interfejsy. Na pierwsze
uruchomienie wybierz `RETAILOPS_SEED_DATA_PROFILE=demo`, korzystający z małego
zestawu w repozytorium. Plik przykładowy zawiera lokalne dane demonstracyjne;
nie służy do konfiguracji publicznego środowiska.

```bash
make compose-up
make compose-seed
```

Odpowiednik bez Make:

```bash
COMPOSE_PROFILES=dev,observability docker compose up --build -d
make api-install
services/api/.venv/bin/python -m data.seed_files --profile small
COMPOSE_PROFILES=seed docker compose run --rm --no-deps seed
```

Compose uruchamia PostgreSQL, migracje Alembic, API, frontend,
Redpandę z inicjalizacją tematów oraz Prometheus i Grafanę. Dane ładujesz
osobnym poleceniem `compose-seed` tylko dla nowej bazy lub świadomego ponownego
importu. Profil danych
`RETAILOPS_SEED_DATA_PROFILE=small` jest domyślny; `demo` daje mniejszy zbiór do
szybkiej demonstracji. `make compose-seed` przygotowuje brakujące CSV wybranego
profilu; dane skalowane są generowane lokalnie i ignorowane przez Git.
Istniejący kompletny katalog pozostaje bez zmian. Zadanie `seed` odtwarza zawartość tabel aplikacyjnych,
więc jego ponowne wykonanie usuwa wcześniejsze zmiany w tych danych.

| Usługa | Domyślny adres |
|---|---|
| Panel RetailOps | <http://localhost:3000> |
| Dokumentacja API | <http://localhost:8000/docs> |
| Stan procesu API | <http://localhost:8000/health> |
| Gotowość API i bazy | <http://localhost:8000/ready> |
| Prometheus | <http://localhost:9090> |
| Grafana | <http://localhost:3001> |
| PostgreSQL | `localhost:5432` |
| Redpanda Kafka / Admin API | `localhost:19092` / <http://localhost:19644> |

Porty i lokalne dane logowania są konfigurowane przez `.env`. Przy jego
niezmienionych wartościach przykładowych Grafana używa `admin` / `retailops`.
Przełączanie użytkowników w panelu służy wyłącznie do demonstracji uprawnień,
nie potwierdza tożsamości. Tego Compose nie używaj do udostępniania aplikacji
innym użytkownikom; opis granicy znajduje się w [instrukcji bezpieczeństwa](../security/demo-auth-boundary.md).

Przed startem można sprawdzić wszystkie profile i nakładkę monitoringu:

```bash
make compose-config
```

Kontrola odrzuca każdy port publikowany poza loopback, także przy próbie
`HOST_BIND=0.0.0.0`. `make compose-ci` sprawdza również adresy faktycznie
opublikowanych portów w izolowanym uruchomieniu.

## Sprawdzenie i codzienna obsługa

```bash
docker compose --profile dev --profile observability ps -a
make compose-smoke
make streaming-smoke
make observability-smoke
```

`streaming-smoke` odczytuje listę topiców, odpowiedzi API, nazwy metryk oraz
targety i reguły Prometheusa. Nie publikuje i nie przetwarza nowego zdarzenia,
więc nie dowodzi przepływu producent → broker → konsument. Szczegóły:
[broker lokalny](streaming.md).

Aby obejrzeć logi:

```bash
docker compose --profile dev --profile observability logs --tail=100 api migrate
```

Zatrzymaj projekt i później uruchom go ponownie bez ponownego ładowania danych:

```bash
make compose-down
make compose-up
```

`compose-down` usuwa kontenery i sieć projektu, ale zachowuje nazwane wolumeny
PostgreSQL, Redpandy, Prometheusa i Grafany. `compose-up` wykonuje migracje,
lecz nie uruchamia seeda. Odpowiednik zatrzymania bez Make:

```bash
docker compose --profile dev --profile observability down --remove-orphans
```

Jawny reset całego projektu usuwa również te wolumeny. Po nim uruchom usługi
i załaduj dane od nowa:

```bash
make compose-reset
make compose-up
make compose-seed
```

Sam `compose-seed` też zastępuje tabele aplikacyjne. Przy własnym
`COMPOSE_PROJECT_NAME` zachowaj tę samą nazwę projektu we wszystkich
poleceniach. `make db-down` zachowuje wolumeny; `make db-reset-seed-small`
i `make db-reset-seed-medium` wykonują jawny reset przed importem.

## Praca nad kodem

Make używa Python 3.11 i tworzy środowisko `services/api/.venv`. Frontend wymaga
Node/npm; używaną wersję Node określa [Dockerfile](../../frontend/Dockerfile).

```bash
make install
```

Dla API uruchomionego bez kontenera potrzebujesz działającej lokalnej bazy,
migracji i danych. Poniższe polecenia ładują demonstracyjne dane do bazy
wskazanej przez `DATABASE_URL`:

```bash
make db-up
make api-migrate
make api-seed-demo
```

Następnie uruchom API; przykład połączenia odpowiada niezmienionej `.env.example`:

```bash
cd services/api
DATABASE_URL=postgresql://retailops:retailops@localhost:5432/retailops \
  .venv/bin/uvicorn app.main:app --reload
```

Jeśli API w Compose już zajmuje port 8000, zatrzymaj jego kontener przed
uruchomieniem Uvicorn. Zmiany użytkownika, hasła lub portu bazy w `.env` muszą
być odzwierciedlone w podanym adresie połączenia. Sam Uvicorn nie korzysta z
mechanizmu wczytywania `.env` przez Make.

Frontend można rozwijać z odświeżaniem Vite, pozostawiając backend w Compose:
[instrukcja frontendu](frontend.md).

## Konsument zdarzeń

Compose tworzy broker i tematy, ale nie uruchamia osobnej usługi konsumenta.
Po instalacji zależności i uruchomieniu bazy/brokera wykonaj w osobnym terminalu:

```bash
make broker-topics
make realtime-consumer
```

To długotrwały proces uruchamiany na hoście. Zapisuje przetworzone zdarzenia
i metryki w PostgreSQL. Panel `/live-operations` odczytuje te dane; samo
uruchomienie pustego brokera nie wygeneruje ruchu biznesowego.

W razie problemów przejdź do [diagnostyki lokalnej](../runbooks/local-troubleshooting.md).
