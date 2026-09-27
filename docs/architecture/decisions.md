# Obowiązujące decyzje techniczne

Ten dokument wyjaśnia podział odpowiedzialności obecnego kodu.
[Architektura](overview.md) pokazuje komponenty, a
[otwarte ustalenia](../audits/open-findings.md) wskazują konkretne problemy.

## Dane, kontrakty i migracje

**PostgreSQL jest bazą danych operacyjnych.** Relacje, ograniczenia i transakcje
obejmują dane katalogu, sprzedaży, zapasów oraz historię workflow. Zmiany schematu
wprowadza się kolejnymi rewizjami [Alembic](../../services/api/alembic/versions/).
Migracje wykonuje się przed seedem i uruchomieniem API; dane demonstracyjne nie zastępują
definicji schematu.

**SQLAlchemy Core służy do deklarowania migracji, Psycopg do zapytań aplikacji.**
[Konfiguracja Alembic](../../services/api/alembic/env.py) korzysta z SQLAlchemy,
a [połączenia aplikacji](../../services/api/app/db/connection.py) i repozytoria
z jawnego SQL oraz Psycopg. Nie utrzymujemy równoległego modelu ORM.
Konsekwencją jest ręczne utrzymywanie mapowania kolumn i granic transakcji;
zapytania muszą pozostać parametryzowane.

**Pydantic opisuje i waliduje dane API/domeny.** Modele transportowe nie są
modelami ORM ani źródłem automatycznego tworzenia tabel. Zmiana kontraktu API
wymaga sprawdzenia konsumentów i testów, a zmiana przechowywania danych migracji.

**Historia zastosowanych migracji pozostaje niezmienna.** Manifest wydania
wiąże obraz z rewizją Alembic i hashem historii. Zmiana schematu wymaga jawnego
planu kompatybilności; zasady opisuje [polityka wydania](../governance/releases.md).

## Walidacja i wydania

**GitHub Actions odpowiada za wymagane kontrole merge.** `required-result`
agreguje właściwe bramki domenowe; reguły doboru i wyników są w
[kontrakcie CI](../governance/github-actions-ci.md). Ochrona `main` jest opisana
oddzielnie w [governance](../governance/branch-protection.md).

**Workflow GitHub publikuje wydania GHCR, Jenkins waliduje lokalny stack.**
[Release workflow](../../.github/workflows/release.yml) testuje, skanuje,
publikuje i weryfikuje te same artefakty po digest. [Jenkinsfile](../../Jenkinsfile)
wykonuje checkout, kontrole kodu/danych i izolowane próby Compose/monitoringu.
Jenkins nie jest właścicielem chmurowego apply ani wdrożenia. Procedury i podział
kontroli są w [przewodniku CI/CD](../guides/ci-cd.md).

**Rollback używa zachowanego artefaktu.** Ponowny build tego samego commita nie
gwarantuje identycznego obrazu. Tożsamość wyniku, predecessor, kontrola migracji
i dowody są częścią [polityki release](../governance/releases.md).

## Infrastruktura i tożsamość

**Środowisko składa małe moduły Terraform.** `infra/environments/dev` jest
rootem kompozycji, `infra/modules` zawiera moduły, a `infra/state-backend` ma
osobny lifecycle trwałego stanu. Rozdzielenie chroni backend przed rutynowym
cleanup środowiska. Szczegóły: [infrastruktura](../guides/infrastructure.md).

**Planowanie nie nadaje praw wdrożeniowych.** Dostęp CI do AWS korzysta z OIDC
i zaufania ograniczonego do repozytorium oraz chronionego `main`. Obecny dostęp
do odczytu jest udokumentowany w [dowodzie AWS](../evidence/aws/2026-09-26-state-drift.md).
Wybrane operacje discovery wymagają zakresu zasobów `*`; nie uzasadnia to
wildcard write ani AdministratorAccess. Aktywacja state dodaje uprawnienia do
dokładnego lockfile, a zapis state i apply pozostają odrębną odpowiedzialnością.

**Backend dev używa S3 z natywnym lockingiem i KMS.** Wersjonowanie, prywatność,
TLS, wyłączenie ACL i osobne polityki plan/operator są zdefiniowane w
[backendzie](../reference/terraform-state-backend.md). Wdrożenie i testy live
realizuje się według [runbooka](../runbooks/terraform-remote-state.md).

**Compose i kind są lokalnymi środowiskami demonstracyjnymi.** Demo identity
nie stanowi uwierzytelnienia produkcyjnego; próby lokalne nie zastępują walidacji
chmury, HA ani odzyskania po utracie klastra. Zakres rozszerzenia AWS ustala
[plan aktywacji](../plans/aws-activation.md), a docelowe AI ma oddzielne
[kontrakty i plan](../plans/ai/README.md).
