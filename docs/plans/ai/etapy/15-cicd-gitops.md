# 15 — Zamknij CI/CD i GitOps

**Repozytorium główne:** AI; zgodność bramek i kontraktów obejmuje również RetailOps. **Zależność:** 14. **Status:** instrukcja do wdrożenia.

## Cel

Połączyć wymagane bramki PR, niezmienne artefakty release'u i Argo CD tak, aby każdą zmianę dało się prześledzić, odrzucić albo odtworzyć. Podstawowe workflows obowiązują od 01; tutaj domykamy cały przepływ dostarczania.

Zasady release'u opisuje [lifecycle](../kontrakty/ml-api-lifecycle.md), awarie i rollback [runbook](../runbooki/operacje-i-awarie.md).

## Kolejność małych PR-ów

1. **Macierz zmian i wymagany wynik.** Wykorzystaj wzorzec `.github/workflows/required-ci.yml` oraz agregujący `required-result` w RetailOps; w AI wprowadź analogiczny jeden wynik wymagany przez branch protection. Detector uwzględnia kod, kontrakty, generator/features, dependency lock, modele, prompt/tools/corpus, Docker/Helm, Terraform, workflow i docs. Wymagany aggregator uruchamia się zawsze; nie opieraj całego wymaganego workflow na paths powodujących pominięcie raportu. Nieznany wynik, błąd detektora, `cancelled`, błąd wymaganej pracy lub nieoczekiwane `skipped` oznaczają failure. Skip jest dopuszczalny tylko, gdy macierz jawnie uznała job za niewymagany.
2. **Bramki PR i test macierzy.** Uruchamiaj docs/links, format/lint/typecheck, unit/integration, zgodność migracji, schemas/OpenAPI/events/tools, backward compatibility, tiny deterministic ML i fake-agent smoke, secret/dependency/container scan, Helm/Kubernetes i Terraform validation odpowiednio do zakresu. Testy obejmują success i failure ważnych granic. Sprawdź co najmniej zmianę tylko kontraktu, tylko ML, tylko corpus/prompt, tylko workflow oraz docs-only. Kontrolowany wadliwy PR musi rzeczywiście zablokować merge. Nie uruchamiaj pełnego HPO, dużych danych ani płatnego Bedrock na zwykłym PR.
3. **Bezpieczeństwo workflow.** Domyślne `contents: read`, uprawnienia zwiększane per job; actions przypięte do SHA, zależności z locka. Untrusted/fork PR bez sekretów, push obrazu i AWS identity; nie uruchamiaj niezaufanego kodu w uprzywilejowanym `pull_request_target`. GitHub OIDC tylko w chronionych jobach wymagających AWS, z ograniczonym trust policy dla repo/ref/environment. Dodaj concurrency grupy, limity czasu i retencję artefaktów. CI logi i Terraform plans traktuj jako potencjalnie wrażliwe.
4. **Build i komplet release'u.** Z zatwierdzonego commitu buduj obraz, skanuj, twórz SBOM i provenance, publikuj do zatwierdzonego registry oraz zapisz digest. Semver/SHA są opisem; deployment używa digestu. Nie używaj `latest`. Rejestr release'u wiąże image digest, chart version, GitOps commit, modele MLflow z numerami wersji i checksumami, agent config, corpus/embedding/index, feature/output schema oraz migration version.
5. **Rozdziel promocje.** Trening i model release są osobnym kontrolowanym workflow z wejściem dataset/config ID, ewaluacją, kartą i audytem. Zmiana aliasu `champion` sama nie zmienia runtime. Wybór zatwierdzonego aliasu może rozwiązać wersję na etapie przygotowania release'u, ale GitOps zapisuje niezmienną wersję i hash. Zmiana agenta/promptu/tools/index wymaga odpowiednich golden/security gates. Porażka modelu lub agenta nie może utworzyć deployment PR. Bedrock live smoke jest osobnym ograniczonym workflow.
6. **Argo CD i desired state.** Trzymaj `gitops/applications` oraz local/aws-dev values w repo AI. PR aktualizuje zatwierdzony zestaw release refs; Argo synchronizuje wskazany commit. Local może mieć auto-sync/prune/self-heal po ograniczeniu zarządzanych zasobów. Dla AWS wybierz jawnie politykę sync i chronione środowisko. Migracje expand wykonuj przez reviewed Job/PreSync, bez auto-migrate w każdym podzie. Destrukcyjny contract wykonuje się dopiero po oknie kompatybilności, backupie i osobnej decyzji.
7. **Reconciliation i recovery.** Wywołaj kontrolowany drift w zasobie demo i sprawdź wykrycie oraz powrót do Git. Następnie wadliwy release, nieudaną migrację lub brak modelu: zapisz rzeczywisty stan częściowego rolloutu. Odtwórz ostatni zgodny komplet przez GitOps PR/revert i odpowiedni runbook, zweryfikuj `/version`, serving, jobs, agent/index oraz integralność wyników. W trybie auto-sync nie polegaj na ręcznym rollbacku Argo bez korekty desired state w Git.

## Kontrakt niepowodzeń

| Niepowodzenie | Oczekiwany wynik |
|---|---|
| Wymagana bramka PR lub detektor | Wymagany check czerwony, merge zablokowany |
| Blocking scan lub niezgodny artifact | Brak zatwierdzonego release'u/deploymentu |
| Candidate/evaluation/drift gate | Runtime bez zmiany; zachowany raport odrzucenia |
| Argo sync albo post-sync smoke | Release failed, jawna ocena częściowego stanu i uruchomiony recovery |
| Błąd migracji | Brak dalszej promocji; zachowany backup/log i zgodność ze starym runtime sprawdzona |
| Terraform plan poza zakresem | Brak apply |
| Zmiana MLflow aliasu po wdrożeniu | Restart nadal ładuje wersję z release'u |
| Bedrock outage | Kontrolowana degradacja agenta, niezależne API ML nadal działają |

Nie deklaruj, że nieudany sync zawsze zostawia poprzednią zdrową rewizję: część zmian może być już zastosowana. Rollback image bez zgodnego modelu/config/index i schematu DB nie jest pełnym rollbackiem.

## Artefakty i Definition of Done

Workflow files, macierz paths/jobs, test fail-closed agregatora, dowód branch protection, test wadliwego PR, lockfile, SBOM/provenance/scan summary, release manifest, GitOps PR, Argo synced/healthy i drift/recovery evidence. [Szablony](../szablony/karty-i-evidence.md) określają metadane dowodów.

Etap kończy się przejściem rzeczywistego łańcucha PR → wymagane checks → immutable build → reviewed GitOps update → kind sync → smoke → odtworzenie poprzedniego zgodnego release'u. Wszystkie wersje potwierdza runtime. Etap 15 wraz z 16A oraz live Bedrock smoke z 12 zamyka lokalny zakres portfolio **K2**.

## Gotowy prompt do Codex

```text
Wykonaj etap 15 na działającym chart/kind. Zachowaj i rozszerz wzorzec required-ci /
required-result; zbuduj fail-closed macierz ścieżek i udowodnij, że błędny PR blokuje
merge. CI dla untrusted PR nie otrzymuje sekretów ani AWS credentials. Dodaj
immutable build, SBOM/provenance, chroniony OIDC, release manifest i GitOps PR.
Runtime ma używać numerów wersji MLflow+checksum, nigdy zmiennego aliasu. Rozdziel
release app/model/agent oraz ewaluacje. Wdróż przez Argo CD, sprawdź drift, failed
sync/migration i odtwórz spójny zestaw image/model/config/index/schema przez Git.
Nie twierdź, że poprzednie środowisko zawsze pozostaje zdrowe; wykaż konkretny stan
oraz recovery. Opisz ograniczenia i zaktualizuj evidence oraz runbook.
```
