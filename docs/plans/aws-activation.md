# Aktywacja środowiska AWS

Ten plan dotyczy następnego świadomie uruchamianego środowiska chmurowego.
Nie jest instrukcją utrzymywania obecnego deploymentu. Punktem wyjścia jest
[przegląd AWS/state](../evidence/aws/2026-09-26-state-drift.md);
[przewodnik infrastruktury](../guides/infrastructure.md) opisuje dostępny kod.

## Kolejność prac

| Etap | Zakres | Warunek przejścia dalej |
|---|---|---|
| 1. Właściciel i zakres | Określić konto, region, runtime, czas działania, budżet, dane oraz zasoby trwałe i tymczasowe. Ponowić inventory i ustalić właściciela każdego istniejącego state. | Aktualny spis zasobów i plan cleanup; brak nieustalonego stanu wymagającego odzyskania. |
| 2. Backend | Przygotować oddzielny bootstrap S3/KMS, chronić jego własny state i kopię odzyskiwania, przypisać operatora oraz ograniczone uprawnienia state/lock. | Readback kontroli bucketu/KMS; zweryfikowane wykluczanie równoczesnych operacji i odtworzenie wersji stanu. Migracja wyłącznie wtedy, gdy istnieje rzeczywisty stan źródłowy. |
| 3. Spójna konfiguracja | Połączyć wybrany compute z siecią, registry, tożsamością i magazynem sekretów. Dla EKS podłączyć odpowiednie moduły, dostęp do API klastra i wyjście do wymaganych usług. | Plan używa dokładnie parametrów przyszłego deploymentu; walidacja, skany oraz przegląd tras, dostępu i kosztów przechodzą. |
| 4. Dostęp aplikacji i dane | Rozwiązać granicę uwierzytelnienia, trwałość bazy/brokera, backup, retencję i odzyskiwanie poza hostem/klastrem. | Udokumentowany model dostępu oraz próba odzyskania danych odpowiednia dla tego środowiska. |
| 5. Dostarczenie | Wdrożyć zatwierdzony artefakt po digest wraz z jego SBOM/provenance; ustalić oddzielną tożsamość apply/deploy i zakres zmiany. | Działające smoke i decyzje biznesowe, zachowana tożsamość obrazu, monitoring oraz rollback dla użytej wersji aplikacji i schematu. |
| 6. Zakończenie | Usunąć zasoby tymczasowe według zatwierdzonego planu; zachować wyłącznie wcześniej wskazane zasoby trwałe. | Kontrola inventory i stanu po cleanup, zapis pozostawionych zasobów, późniejszy przegląd rozliczeń. |

## Zasady wykonania

Plan istniejącego wdrożenia musi używać jego autorytatywnego stanu i rzeczywistych
parametrów. Obecny runner obsługuje dev example; przed użyciem innych parametrów
trzeba rozszerzyć i sprawdzić jego kontrakt. Pusty baseline nie zastępuje
odzyskania stanu ani importu istniejących zasobów.

Rola GitHub do planowania pozostaje odrębna od operatora zmieniającego zasoby.
Odczyt infrastruktury i zapis dokładnego pliku `.tflock` mają osobne zakresy
uprawnień. Istniejących ról nie należy przejmować do nowego state bez jawnej
decyzji o własności.

Kosztorys powstaje przy wyborze konfiguracji i okresu działania. Obejmuje także
storage, transfer, adresy, load balancery, sieć, logi, rejestr obrazów i KMS.
Przykładowa wartość budżetu w Terraform nie jest kosztorysem ani limitem wydatków;
powiadomienia wymagają konfiguracji rzeczywistych odbiorców poza Git.

Zmiana schematu wymaga własnego planu kompatybilności i odzyskania. Istniejąca
próba rollbacku przy zgodnym schemacie nie daje dowodu odwracalności przyszłych
migracji. Dowód aktywacji zapisuje commit, region, rzeczywisty zakres, digests,
wyniki kontroli, pomiary oraz cleanup, bez publikowania state lub sekretów.

Procedury: [backend i migracja](../runbooks/terraform-remote-state.md),
[drift](../runbooks/terraform-drift-check.md),
[release](../runbooks/registry-release.md),
[rollback](../runbooks/application-rollback.md),
[cleanup AWS](../runbooks/aws-cleanup-runbook.md).
