# 16 — Przygotuj Terraform i wykonaj pokaz AWS

**Repozytoria:** RetailOps + AI. **Zależność zakończenia całego etapu:** 15. **Status:** instrukcja; definicje infrastruktury nie dowodzą istniejących zasobów.

## Cel, dwa podetapy i kolejność

**16A — IaC i plan** można rozpocząć równolegle po 01, gdy znany jest kontrakt wejść infrastruktury. Nie czekaj z projektowaniem, walidacją i kosztorysem do końca prac ML. Zamknięte 16A jest warunkiem K2: cały lokalny zakres 00–15 wraz z ograniczonym live Bedrock smoke z 12.

**16B — kontrolowany pokaz AWS** wykonaj po 15, zaliczonym 16A i wyborze konkretnego scenariusza. Razem z odbiorem 17 zamyka K3/portfolio v1. Plan-only nie jest cloud deploymentem.

## Stan wejściowy i ownership

Sprawdź definicje `vpc_id`, `public_subnet_ids` i `private_subnet_ids` we właściwym entry poincie `infra/environments/dev/`. Wykorzystaj istniejące outputy; nie buduj domyślnie drugiego VPC. Ustal mechanizm przekazania wartości i ewentualne brakujące outputy security groups. Przed użyciem sprawdź aktualny kod, state oraz faktyczne zasoby konta.

RetailOps pozostaje właścicielem swojej foundation/state; AI ma odrębny state i zasoby. Remote-state consumer otrzymuje tylko konieczny dostęp, bo sam state może zawierać dane wrażliwe. Preferuj jawny zatwierdzony kontrakt inputs/outputs lub odpowiednio ograniczone publikowanie konfiguracji. Backend, locking, szyfrowanie i bootstrap muszą mieć właściciela; nie kopiuj stanu do Git.

## 16A — małe PR-y

1. **ADR wariantu cloud i kosztów.** Zapisz konto, region, czas działania, ownera, tags, zakres danych, schemat ruchu, tożsamości i zasoby. Wybierz jeden wariant 16B z tabeli. Oszacuj koszty EKS/RDS/storage/egress/Bedrock i koszt stałych elementów, także LB, NAT, endpoints oraz logs. Budżet AWS jest opóźnionym alertem, nie twardym limitem wydatków; ogranicz także max requests/tokens/concurrency, lifetime zasobów oraz liczbę uruchomień.
2. **Moduły i wyłączone kosztowne domyślne zasoby.** Przygotuj AI ECR, S3 artifacts/datasets, PostgreSQL/pgvector, Bedrock IAM, workload identity, secrets, observability i budget. EKS/shared cluster ma jawny wariant i `enable_eks=false` domyślnie. Dla RDS sprawdź wsparcie wymaganej wersji pgvector i backup/migration policy przed apply. Deklaracje modułu mogą być gotowe bez jego uruchomienia; oznacz ten status.
3. **Zasady IAM i sieci.** GitHub OIDC ma odrębne role plan/apply/publish z trust policy na repo/ref/environment. Runtime ma osobną tożsamość, a agent i indexing job dostają rozdzielone, ograniczone uprawnienia Bedrock do zatwierdzonych modeli/profili i regionu. API i MLflow mają różne DB users/schemas; AI nie uzyskuje dostępu do DB RetailOps. Baza pozostaje prywatna. AWS endpoint egress ma jawny routing/cost trade-off; nie dodawaj NAT/MSK tylko dla podobieństwa środowisk.
4. **Storage i sekrety.** S3: public access block, versioning, encryption, lifecycle, ownership, ograniczone prefixy i checksums. ECR: immutable tags, scanning, lifecycle i kontrolowany dostęp. Sekrety przez środowiskowe referencje/Secrets Manager, nie Git/values. Zdefiniuj, które modele, snapshoty, raporty i backupy zachowujemy, gdzie i przez ile; retencja także kosztuje. KMS tylko tam, gdzie ma uzasadnienie i znany lifecycle.
5. **Walidacja i plan.** Wprowadź format/init backend-disabled/validate, TFLint, Checkov oraz testy kluczowych reguł modułów. PR bez zaufania nie dostaje credentials. Walidacja offline albo render konfiguracji nie jest pełnym planem konta. Authenticated plan odbywa się przez chroniony OIDC i zapisuje sanitized summary: create/change/destroy, ryzyka, koszty, brak duplikacji VPC. Nie publikuj surowego planu/state z sekretami. Plan i cleanup review są gate przed 16B.

### Gate 16A

Kontrakt inputs/ownership, wersjonowane moduły, wybrane profile, pozytywna walidacja/lint/security, przejrzany plan, role OIDC/IAM, kosztorys, retencja i konkretna procedura cleanup. Testy wykrywają publiczny bucket/DB, zbyt szerokie uprawnienia, brak tags i przypadkowe uruchomienie kosztownego profilu. Nierozstrzygnięte wartości/provider auth muszą być jawnie oznaczone; nie nazywaj niepełnego planu zweryfikowanym planem konta.

## 16B — wybierz i wykonaj jeden spójny wariant

| Wariant | Rzeczywiście uruchamiane | Co wolno deklarować |
|---|---|---|
| Lokalny Kubernetes + AWS | kind, kontrolowany runtime ze skonfigurowaną czasową tożsamością; ECR, S3, Bedrock oraz wybrane IAM/secrets/monitoring | „Hybrydowy pokaz lokalny + AWS”; bez twierdzenia o EKS/RDS deployment, jeśli ich nie uruchomiono |
| Ephemeral/shared EKS | EKS lub zatwierdzony współdzielony klaster, workload identity, obraz z ECR, S3/Bedrock; opcjonalnie prywatny RDS | „Deployment na EKS” tylko po health/E2E evidence; stan RDS opisany osobno |

W obu wariantach pokaż rzeczywisty ECR push/pull, kontrolowany zapis/odczyt S3 i ograniczone wywołanie Bedrock z runtime. Plan modułu RDS nie oznacza działającej bazy. Lokalny runtime używa krótkotrwałej, jawnie opisanej tożsamości (np. sesji SSO/STS), bez statycznych kluczy; nie nazywaj jej EKS workload identity. EKS korzysta z wybranej wspieranej workload identity. Każdy wariant musi mieć dowód polityk dla wykorzystanych usług i jawny status pozostałych modułów.

### Małe kroki pokazu

1. Sprawdź aktywne konto/region/tożsamość i inventory zasobów przed startem. Powiąż plan z commitem, konfiguracją oraz chronionym środowiskiem. Apply wykonuj wyłącznie po zaakceptowanym konkretnym planie i zgodnie z istniejącą autoryzacją; publikacja tego dokumentu nie wykonuje ani nie zatwierdza przyszłego apply.
2. Zastosuj minimalny plan; zapisz wynik i rzeczywiste zasoby. Publikuj zatwierdzony digest, wgraj manifest/mały artefakt do właściwego S3 prefixu i odczytaj z kontrolą checksum.
3. Uruchom wybrany runtime, migracje i smoke. Potwierdź `/version`, approved model/config/index, odczyty predykcji oraz bounded Bedrock chat/embedding. Nie odtwarzaj całego treningu na drogim klastrze podczas pokazu.
4. Sprawdź negatywnie niedozwolony model/region/prefix/sekret bez wypisywania sekretów. Kontrolowane odmowy muszą mieć evidence, a dozwolona ścieżka nadal działać. Potwierdź, że agent outage nie wyłącza klasycznych API.
5. Zapisz koszty szacowane oraz dostępny później koszt rzeczywisty; podaj opóźnienie raportowania. Dowody obejmują identity i typ źródła credentials, bez ich wartości.
6. Wykonaj cleanup według runbooka i porównaj inventory account/region przed/po. Usuń kosztowne zasoby będące własnością pokazu. Nie niszcz foundation ani współdzielonych zasobów RetailOps. Świadomie zachowane artefakty i koszty opisz na allowliście z ownerem/terminem.

## Cleanup to część odbioru

Plan destroy jest weryfikowany jak apply. Przed usunięciem DB wyeksportuj potrzebne wyniki/backup i dowody, zdefiniuj politykę final snapshot. Wersjonowany S3 wymaga uwzględnienia wszystkich wersji i delete markers, ECR wszystkich obrazów objętych cleanup. Zasoby utworzone pośrednio przez kontrolery (LB, volumes), snapshots, log groups, secrets i sieciowe pozostałości mogą przetrwać sam `terraform destroy`. Sprawdź każde konto/region/prefix użyte w pokazie; nie stosuj wildcard cleanup obejmującego cudze zasoby.

## Artefakty i Definition of Done

`16A`: plan/validation summary, ADR, input/identity contract, security/cost report i przetestowany lokalnie scenariusz cleanup. `16B`: reviewed apply, inventory before/after, ECR digest, S3 checksum, runtime health, Bedrock smoke, ograniczenia uprawnień, cost record oraz cleanup z ewentualną listą zachowanych zasobów. W [szablonie evidence](../szablony/karty-i-evidence.md) wskaż dokładnie `executed`, `static` lub `not tested`.

Cały etap 16 kończy się, kiedy pokaz wybranego wariantu działał, jego granice są uczciwie opisane i cleanup został potwierdzony. Nie wystarczy screenshot konsoli ani sam plan.

## Gotowy prompt do Codex

```text
Przygotuj etap 16A po ustaleniu kontraktów z 01: Terraform, input/ownership istniejącej
RetailOps VPC, security, OIDC, plan, koszty i cleanup. Outputy VPC/public/private
subnets już istniały w infra/environments/dev; nie twórz ich ani VPC ponownie bez
wykazanej potrzeby. Oddziel AI state i IAM, domyślnie wyłącz EKS/RDS kosztownego
profilu. Zachowaj moduły PostgreSQL, identity, secrets, observability i budget także
gdy wybrany showcase ich nie uruchamia. Budżet nie jest hard cap. 16B wykonuj tylko
w autoryzowanym, chronionym trybie po 15 i zaakceptowanym planie: wybierz local+AWS
lub EKS, pokaż rzeczywiste ECR/S3/Bedrock/runtime, sprawdź ograniczenia uprawnień,
a następnie wykonaj i zweryfikuj cleanup bez naruszenia zasobów współdzielonych.
Zapisz inventory konto/region przed/po, pozostałe S3 versions/ECR images/backups/logs,
koszty i ograniczenia. Nie deklaruj uruchomionego EKS/RDS na podstawie planu.
```
