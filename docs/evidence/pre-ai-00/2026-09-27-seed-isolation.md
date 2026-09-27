# Izolacja testów seeda — 27.09.2026

Kod: `667f3494c9f69f4fee3283aca577c408e89fa545`, branch `prep/before-ai-00`.
**Wynik: baza źródłowa i śledzone dane pozostają bez zmian; testowe bazy są
usuwane także po błędzie. Nie ma otwartych prac wymaganych przed AI 00.**

## Zakres implementacji

[Fixture seeda](../../../services/api/tests/test_seed_data.py) buduje osobne
URL dla bazy administracyjnej `postgres` i losowej bazy testowej. Dekoduje
klucze query i usuwa wszystkie `dbname`, także powtórzone i zakodowane.
Pozostałe opcje połączenia są zachowane. `current_database()` potwierdza
wybraną bazę przed CREATE/DROP i przed przekazaniem testowego URL migracjom
oraz seedowi. Niezgodność blokuje przygotowanie testów; baza utworzona przed
błędem weryfikacji również jest sprzątana.

Nowe [testy regresji](../../../services/api/tests/test_seed_database_isolation.py)
sprawdzają wybór bazy przez Psycopg i SQLAlchemy, zachowanie parametrów,
odmowę dla niezgodnej rzeczywistej bazy oraz cleanup po wyjątku. Nie wymagają DB.
Zwykły seed aplikacji i `make api-integration-test` nadal są jawnymi operacjami
zmieniającymi wskazaną bazę; izolacja opisana tutaj dotyczy `test_seed_data.py`.

## Rzeczywista weryfikacja

Środowisko: macOS arm64, Python 3.11.15, pytest 9.0.3. Osobny kontener
PostgreSQL 16 Alpine używał tmpfs, automatycznego usunięcia i portu wyłącznie
na `127.0.0.1`. Tożsamość lokalnego obrazu, sumy testowanego kodu i wyniki:
[seed-isolation-verification.json](seed-isolation-verification.json).
Próby DB zakończyły się o `2026-09-27T15:10:42Z`; po uporządkowaniu importów
pliku regresji ponowiono jego testy bez DB. Fixture integracyjna zachowała
identyczny SHA-256. Kod aplikacji i śledzone dane nie były zmieniane.

W jednorazowej bazie źródłowej `source_probe` wykonano migracje i zapisano
produkt kontrolny `ISOLATION-GUARD`, którego nie ma w seedzie demo. Po każdej
próbie porównywano stan początkowy z sumą pełnego dumpa schematu oraz danych,
sumami 19 śledzonych plików `data/demo` i listą baz `retailops_seed_test_*`.

| Próba | Wynik |
|---|---|
| Regresje wyboru bazy, profile seeda, diagnostyka DB | 27 passed; w tym 20 nowych regresji. |
| Zwykły URL z `/source_probe` | 10 passed, 0 skipped. |
| `?dbname=source_probe` | 10 passed, 0 skipped. |
| Powtórzenie tego samego URL z `dbname` | 10 passed, 0 skipped. |
| `?dbname=postgres&%64bname=source_probe` | 10 passed, 0 skipped. |
| `?db%6eame=source_probe&application_name=seed_probe&connect_timeout=3` | 10 passed, 0 skipped. |
| Wyjątek po przygotowaniu fixture, przed pierwszym testem | Oczekiwane 1 failed; cleanup i ochrona danych potwierdzone. |

W każdej próbie DB źródłowy dump i pliki demo zachowały sumy, a po zakończeniu
nie pozostała żadna baza testowa. Kontener po weryfikacji zatrzymano i usunięto;
baza deweloperska nie była używana. Sprawdzenie formatowania oraz Ruff E/F/I
dla obu zmienionych plików także przeszło.

## Polecenia i artefakty

Z katalogu głównego repo, testy bez DB:

```bash
env -u DATABASE_URL PYTHONDONTWRITEBYTECODE=1 services/api/.venv/bin/python -m pytest \
  services/api/tests/test_seed_database_isolation.py \
  services/api/tests/test_seed_data_profiles.py \
  services/api/tests/test_db_availability_diagnostics.py \
  -q --junitxml=ci-cd/reports/pre-ai-00-seed-isolation/unit.xml
```

Próby integracyjne uruchamiał lokalny helper
`/private/tmp/retailops_seed_isolation_validation.py`, korzystający wyłącznie
z kontenera oznaczonego `retailops.task=pre-ai-seed-isolation`. Kontener
utworzono przez `docker run --rm --tmpfs /var/lib/postgresql/data` z obrazem
`postgres:16-alpine` i publikacją `127.0.0.1::5432`; helper odczytał przydzielony
port. Dla każdego wariantu z tabeli ustawiał `DATABASE_URL` tego kontenera
i wykonywał:

```bash
REQUIRE_DB_TESTS=1 PYTHONDONTWRITEBYTECODE=1 services/api/.venv/bin/python -m pytest \
  services/api/tests/test_seed_data.py -q
```

Test błędu użył tego samego zestawu z `-x` i pluginem Pytest, którego hook
`pytest_runtest_call` celowo zgłaszał `AssertionError` dla
`test_generator_produces_expected_csv_files`, już po migracjach i seedzie.
Oczekiwany kod wyjścia wynosił 1. Po zakończeniu helper ponawiał porównanie
dumpa, plików i listy baz.

Lokalne logi i JUnit: `ci-cd/reports/pre-ai-00-seed-isolation/` (ignorowane
przez Git). Mały JSON powyżej zachowuje wyniki potrzebne do tego twierdzenia,
bez URL ani poświadczeń. To walidacja lokalna konkretnej poprawki, nie wynik
nowego GitHub Actions ani odbiór całej aplikacji. Pełną decyzję i warunki
dalszych etapów opisuje [audyt AI 00](../ai/00/README.md).
