# RetailOps — dokumentacja

To wspólny punkt wejścia do instrukcji, statusu, audytów i planów projektu.
Dokumenty opisują kod dostępny w repozytorium; wyniki uruchomień mają własne daty
w [indeksie dowodów](evidence/README.md).

## Pierwsza wizyta

1. Przeczytaj [status projektu](STATUS.md), aby poznać dostępne funkcje i ograniczenia.
2. Zobacz [architekturę](architecture/overview.md) i mapę kodu poniżej.
3. Wykonaj [uruchomienie lokalne](guides/local-development.md).
4. Przed zmianą kodu sprawdź [testy](guides/testing.md) i [zasady CI](governance/github-actions-ci.md).
5. Do dalszej pracy używaj [otwartych ustaleń](audits/open-findings.md) i [planu](plans/README.md).

## Gdzie szukać informacji

| Temat | Dokument |
|---|---|
| Stan projektu | [STATUS.md](STATUS.md) |
| Problemy wymagające poprawy | [Audyt: otwarte ustalenia](audits/open-findings.md) |
| Najbliższa praca i rozwój AI | [AI 03](plans/ai/etapy/03-snapshot-curated.md), [kolejność i repozytoria](plans/ai/kolejnosc-i-repozytoria.md), [backlog](plans/ai/backlog.md), [status RAG 11](evidence/ai/11/README.md) |
| Uruchomienie i rozwój aplikacji | [Lokalnie](guides/local-development.md), [frontend](guides/frontend.md), [backend](guides/backend.md) |
| Dane, baza i streaming | [Generator](guides/data.md), [baza](guides/database.md), [broker](guides/streaming.md) |
| Uczenie maszynowe | [Obecna implementacja](guides/ml.md), [ostatnia ocena](evidence/ml/fixed-origin-rf-2026-09-27/README.md) |
| Testy i dostarczanie zmian | [Testy](guides/testing.md), [CI/CD i Jenkins](guides/ci-cd.md), [wydania](governance/releases.md) |
| Infrastruktura | [Terraform/AWS](guides/infrastructure.md), [Kubernetes](guides/kubernetes.md), [plan aktywacji AWS](plans/aws-activation.md) |
| Monitoring | [Instrukcja](guides/observability.md), [SLO](observability/slo.md), [tracing](observability/api-tracing.md) |
| Bezpieczeństwo | [Kontrole i wyjątki](security/controls.md), [granica demo auth](security/demo-auth-boundary.md) |
| Procedury operacyjne | [Spis runbooków](runbooks/README.md) |
| Kontrakty i specyfikacje | [Spis referencji](reference/README.md) |
| Wyniki weryfikacji | [Dowody](evidence/README.md) |
| Decyzje techniczne | [Obowiązujące decyzje](architecture/decisions.md) |
| Utrzymanie dokumentacji | [Zasady aktualizacji](guides/documentation.md) |

## Mapa repozytorium

| Katalog | Zawartość |
|---|---|
| `frontend/` | Interfejs React, klient API, testy przeglądarkowe |
| `services/api/` | FastAPI, reguły biznesowe, repozytoria SQL, migracje i testy |
| `data/`, `events/` | Generator, dane demonstracyjne i kontrakty zdarzeń |
| `ml/` | Cechy, modele, ewaluacja, metadane i batch inference |
| `infra/`, `k8s/` | Terraform oraz manifesty i konfiguracja lokalnego klastra |
| `observability/`, `security/`, `policy/` | Konfiguracja monitoringu, skanerów i polityk |
| `.github/`, `Jenkinsfile`, `Makefile`, `scripts/` | Automatyzacja sprawdzania, wydań i operacji |
| `tests/` | Testy przekrojowe i scenariusze wydajnościowe |
| `ci-cd/reports/` | Generowane, lokalne wyniki narzędzi; nie jest źródłem aktualnego statusu |
| `docs/` | Cała dokumentacja dla osób pracujących z projektem |

`STATUS.md` opisuje możliwości, audyt zawiera tylko otwarte problemy, a `plans/`
opisuje pracę do wykonania. Usunięte i zakończone zadania nie mają tu osobnego
archiwum; historię śledzonych dokumentów przechowuje Git.
