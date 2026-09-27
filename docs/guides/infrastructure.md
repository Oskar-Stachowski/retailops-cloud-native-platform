# Infrastruktura Terraform

Punktem wejścia dla AWS dev jest
[`infra/environments/dev`](../../infra/environments/dev/main.tf).
Konfiguracja składa fundament AWS; uruchomienie aplikacji na EKS wymaga
osobnej integracji. Bieżący zakres weryfikacji konta i stanu opisuje
[dowód AWS/state](../evidence/aws/2026-09-26-state-drift.md), a dalsze wdrożenie
[plan aktywacji AWS](../plans/aws-activation.md).

## Układ i odpowiedzialności

| Ścieżka kodu | Rola | Dokumentacja |
|---|---|---|
| `infra/environments/dev/` | Składa moduły tags, VPC, IAM, ECR, budget i CloudWatch | Ten przewodnik |
| `infra/state-backend/` | Osobny trwały backend S3/KMS i polityki dostępu do state/lock | [Backend stanu](../reference/terraform-state-backend.md) |
| `infra/modules/tags/` | Nazwy i wspólne tagi | [Tags](../reference/terraform/tags.md) |
| `infra/modules/vpc/` | VPC, podsieci i trasy | [VPC](../reference/terraform/vpc.md) |
| `infra/modules/iam/` | Polityka planowania i opcjonalne role | [IAM](../reference/terraform/iam.md) |
| `infra/modules/ecr/` | Repozytoria obrazów i retencja | [ECR](../reference/terraform/ecr.md) |
| `infra/modules/budget/` | Budżet i opcjonalne powiadomienia | [Budget](../reference/terraform/budget.md) |
| `infra/modules/cloudwatch/` | Grupy logów i retencja | [CloudWatch](../reference/terraform/cloudwatch.md) |
| `infra/modules/eks/`, `node_group/`, `iam_oidc/` | Moduły wymagające podłączenia do środowiska | [EKS](../reference/terraform/eks.md), [node group](../reference/terraform/node_group.md), [OIDC](../reference/terraform/iam_oidc.md) |

Pliki w samym `infra/` zawierają wspólne deklaracje i konwencje; nie zastępują
roota środowiska dev. Nazwy korzystają z prefiksu `project-environment`,
a wspólne tagi to `Project`, `Environment`, `Owner`, `ManagedBy`, `CostCenter`
i `Lifecycle`. Wartość `temporary` lub `persistent` opisuje zamiar utrzymania;
nie uruchamia automatycznego usuwania zasobów.

## Walidacja bez poświadczeń AWS

Z katalogu głównego repozytorium, przy Terraform 1.10+ (wersja CI jest zapisana
w workflow), Pythonie 3.11+, TFLint i Checkov:

```bash
make terraform-fmt-check
make terraform-validate
make terraform-state-test
make iac-scan
```

Te kontrole mogą pobierać providery i narzędzia, ale nie tworzą zasobów AWS.
`terraform-validate` inicjalizuje konfigurację z `-backend=false`; nie służy do
sprawdzania istniejącego remote state. Test backendu korzysta z mock providera,
a drill stanu z lokalnego pliku. Raporty trafiają do `ci-cd/reports/`.

## Plan i przegląd istniejącego stanu

[Procedura baseline/drift](../runbooks/terraform-drift-check.md) opisuje wymagane
poświadczenia, `TF_EXPECTED_ACCOUNT_ID`, inventory, komendy i znaczenie wyników.
`make terraform-plan-dev` celowo planuje z pustego stanu; `make terraform-drift`
wymaga istniejącego zarządzanego stanu S3. Żadna z tych komend nie wykonuje apply.

Runner [`scripts/terraform/plan.py`](../../scripts/terraform/plan.py) pracuje
w prywatnej kopii konfiguracji i obsługuje śledzone pliki Terraform oraz
`terraform.tfvars.example` dla dev. Prywatne warianty parametrów wdrożenia
wymagają rozszerzenia tego kontraktu; nie wolno traktować planu przykładowej
konfiguracji jako planu dowolnego istniejącego środowiska.

Plany, state, backend JSON i rzeczywiste parametry pozostają poza Git.
Publikowane raporty zawierają zredagowane wyniki, rewizję i zakres kontroli.
Aktywacja backendu: [remote state](../runbooks/terraform-remote-state.md).
Problemy: [błąd planu](../runbooks/terraform-failed-plan.md).
Zakończenie eksperymentu: [cleanup](../runbooks/aws-cleanup-runbook.md).
