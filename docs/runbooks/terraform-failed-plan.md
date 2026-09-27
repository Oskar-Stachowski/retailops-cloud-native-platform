# Nieudana walidacja lub plan Terraform

Zacznij od raportu `ci-cd/reports/terraform-state/<run>/report.json` lub wyniku
konkretnej bramki IaC. [Procedura plan/drift](terraform-drift-check.md) jest
źródłem komend i klasyfikacji; ta instrukcja pomaga ustalić przyczynę błędu.

## Rozróżnij wynik planu od awarii

Runner [`scripts/terraform/plan.py`](../../scripts/terraform/plan.py) zwraca:

| Kod | Znaczenie | Działanie |
|---:|---|---|
| 0 | Baseline bez state albo brak driftu istniejącego state; sprawdź `classification` | Oceń wynik w jego zadeklarowanym zakresie. |
| 2 | Drift lub zmiana konfiguracji/outputów wymagająca przeglądu | Przejrzyj klasyfikację i oczekiwaną zmianę; to nie awaria providera. |
| 1 | Błąd wejść, konta, backendu, uprawnień, providera lub niepełny plan | Napraw wskazaną przyczynę przed ponowieniem. |

Sam kod `2` z Terraform nie rozstrzyga, czy wykryto drift. Runner analizuje
osobno normalny i refresh-only plan oraz sprawdza, czy state pozostał niezmieniony.

## Diagnoza

| Objaw | Sprawdź i popraw |
|---|---|
| `fmt` / `validate` | Uruchom z root repo `make terraform-fmt-check` i `make terraform-validate`; porównaj argumenty modułu z jego `variables.tf` i `outputs.tf`. |
| Brak providera lub niezgodny lock file | Użyj wersji Terraform z CI i śledzonego `.terraform.lock.hcl`; sprawdź dostęp do registry oraz checksumy platformy. Aktualizacja locka powinna być osobną przejrzaną zmianą. |
| Brak konta lub `aws_account_mismatch` | Sprawdź prywatnie profil, aktualność sesji i `TF_EXPECTED_ACCOUNT_ID`. Konto nie może być wybierane wyłącznie na podstawie przypadkowo aktywnych credentials. |
| Błąd OIDC w GitHub | Sprawdź `main`, zaufanie roli, `AWS_TERRAFORM_PLAN_ROLE_ARN` i `AWS_TERRAFORM_ACCOUNT_ID`; brak apply permissions jest zamierzony. |
| `backend_*` | Porównaj ignored backend JSON z jego przykładem, dokładnym kluczem, regionem i kontem KMS. Sprawdź versioning, szyfrowanie, blokadę public access, ACL i TLS. |
| Brak state, odmowa odczytu lub pusty managed state | Ustal właściwy backend i własność stanu. Tryb baseline nie zastępuje odzyskania istniejącego deploymentu. |
| Błąd locka | Sprawdź właściciela i aktywne operacje. Rola tylko do odczytu AWS potrzebuje również ograniczonego zapisu/usuwania właściwego `.tflock`. |
| Access denied providera | Ustal wymaganą operację i zasób; dodanie szerokich praw zapisu nie jest sposobem naprawy planu. |
| Checkov/TFLint | Oddziel błąd narzędzia od ustalenia; popraw kod albo zastosuj uzasadniony wyjątek z [polityki bezpieczeństwa](../security/controls.md). |
| Nieoczekiwane tworzenie/usuwanie zasobów | Porównaj rewizję, state, workspace i parametry. Runner obsługuje tylko dev example; inne parametry wymagają rozszerzenia jego kontraktu. |

`init -backend=false` służy statycznej walidacji konfiguracji. Nie używaj go
jako naprawy dostępu do aktywnego backendu. Migrację, odzyskanie i ocenę locka
prowadź według [remote-state runbook](terraform-remote-state.md), bez wyłączania
locking ani automatycznego force-unlock.

## Ponowienie i dowód

Po korekcie uruchom właściwą kontrolę: `make iac-scan` dla kodu, ponowne baseline
dla świadomie pustego stanu lub `make terraform-drift` dla istniejącego state.
Zmiany samego runnera sprawdza `make terraform-state-test`.

Runner celowo publikuje bezpieczny typ błędu zamiast surowej diagnostyki
providera. Jeśli potrzeba szczegółów, odtwórz problem w prywatnej sesji operatora
z właściwym backendem i parametrami. Nie publikuj state, planów binarnych,
`terraform show -json`, pełnych ARN ani poświadczeń w raportach CI.

Zapisz rewizję, tryb, kategorię błędu, poprawkę oraz wynik ponowienia.
Udane planowanie nie uruchamia apply; zmiana infrastruktury ma własny zakres
i przegląd zgodnie z [planem aktywacji](../plans/aws-activation.md).
