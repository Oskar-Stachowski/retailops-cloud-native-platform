# 14 — Uruchom system przez Helm na kind

**Repozytoria:** RetailOps + AI. **Zależność zakończenia:** 13. **Status:** instrukcja do wdrożenia.

## Cel i granica etapu

Odtworzyć działającą integrację na czystym lokalnym Kubernetes, łącznie z probes, ograniczeniami dostępu i kontrolowanym rollbackiem. RetailOps zachowuje istniejący deployment Kustomize. Helm pakuje nową usługę AI; migracja całego RetailOps do Helm nie jest warunkiem ani domyślnym zadaniem.

Wstępny Docker/Compose i podstawy platformy powstają w 01, a połączenie sieciowe w 10. Sprawdź [architekturę](../architektura.md), [integrację](../kontrakty/integracja-agent.md) i [operacje](../runbooki/operacje-i-awarie.md).

## Kolejność małych PR-ów

1. **Domknij obraz i Compose.** Jeden wieloetapowy obraz aplikacji udostępnia komendy API, workera i pipeline'ów. Przypnij bazę dla release'u, uruchamiaj jako non-root, z read-only root filesystem i jawnymi mountami tymczasowymi. Modele pobieraj według zatwierdzonych niezmiennych referencji/checksum; nie wypiekaj ich do obrazu. Utrwal Git SHA w labels. Obraz przechodzi load/inference smoke, także dla TensorFlow na deklarowanej platformie. Nie deklaruj ARM64 i AMD64 bez obu testów.
2. **Zweryfikuj wspólną sieć Compose.** W repo bazowym serwisy nazywają się `api`, `db`, `redpanda`; external network i alias `retailops-api` wymagają jawnego overlay. Zapisz ownera sieci, aliasy, porty oraz Kafka advertised listeners rozwiązywalne z AI. AI używa REST i brokera, nigdy bazy RetailOps. Test uruchamia oba projekty osobno i potwierdza, że stop/reset AI nie usuwa źródłowych wolumenów ani współdzielonej sieci. Nie przedstawiaj tej topologii jako zastanej bez testu.
3. **Helm chart i konfiguracja.** Dodaj `deploy/helm/retailops-ai/`: chart, values schema, API/worker Deployments, Services, ServiceAccounts, ConfigMaps, referencje Secrets, opcjonalny Ingress, NetworkPolicy, ServiceMonitor, jobs i CronJobs. Values odróżniają local od AWS i walidują niezmienny image digest oraz release refs. W chart nie ma haseł ani statycznych AWS keys.
4. **Procesy i zdrowie.** API ma startup/readiness/liveness, requests/limits, graceful shutdown i rolling update. Startup daje czas na inicjalizację zatwierdzonego modelu. Readiness odpowiada wymaganym możliwościom tej instancji, a liveness tylko zdolności procesu do pracy; awaria dependency nie uruchamia restart storm. Bedrock nie jest globalnym warunkiem readiness klasycznych API. Worker ma bounded concurrency, consumer group, zatrzymanie fetchu, dokończenie transakcji i właściwe ACK przy SIGTERM.
5. **Jobs, migracje i trwałość.** Feature snapshot, batch inference, drift i refresh RAG uruchamiaj jako Jobs/CronJobs; trening początkowo ręcznie wyzwalanym Job. Ustaw retry/backoff, deadlines, historię, concurrency policy i blokadę podwójnej pracy. Migracja bazy jest pojedynczym kontrolowanym Job, nie działaniem każdego startującego poda. MLflow ma prywatny Service, trwały backend i odrębny artifact store. Backup/restore i utrata lokalnych PVC mają jawne zachowanie. PDB tylko dla konfiguracji, gdzie ma sens; HPA opcjonalnie po pomiarach.
6. **Sieć i uprawnienia.** Stwórz kind z CNI rzeczywiście egzekwującym NetworkPolicy. Wydziel namespace AI i service accounts, namespace-scoped RBAC, drop capabilities, seccomp RuntimeDefault, non-root i mounty. Wprowadź default-deny oraz minimalne reguły DNS, DB, MLflow, telemetry, API RetailOps i brokera. Uzgodnij ingress/egress po obu stronach namespace; istniejące polityki RetailOps mogą nie dopuszczać AI. Dostęp do AWS musi mieć opisaną strategię egress — zwykła NetworkPolicy nie jest allowlistą domen/FQDN. Nie akceptuj szerokiego allow-all jako dowodu selektywnego dostępu.
7. **Czysty deploy, testy i rollback.** Zautomatyzuj nowy klaster, instalację zależności, RetailOps Kustomize i AI Helm, import fixture oraz smoke E2E. Wskaż wymagania RAM/CPU/dysk i wersje narzędzi. Sprawdź kontrolowany update oraz odtworzenie poprzedniego zgodnego release'u. W 15 ten sam chart zostanie objęty Argo CD.

## Sprawdzenia

| Obszar | Sukces | Przypadek negatywny |
|---|---|---|
| Chart | lint, schema, render kilku values, kubeconform, test polityk | Złe values/niezgodny release blokują render lub rollout |
| Probes | Cold start ładuje poprawny model, potem Ready | Brak artefaktu/checksum utrzymuje NotReady; awaria Bedrock nie blokuje read API ML |
| Kontener | UID non-root i zapis tylko w mountach | Zapis do root FS jest odrzucony; aplikacja nadal pracuje |
| Sieć | AI → dozwolone API/broker/DB/DNS działa | Pod spoza dozwolonego namespace/selector nie łączy się do AI i bazy |
| Worker | SIGTERM i wznowienie nie duplikują efektów | Crash między DB commit a ACK kończy się bezpiecznym replay |
| Jobs | Powtórny batch jest idempotentny | Nakładające się uruchomienia nie publikują podwójnych wyników |
| Migracja | Expand umożliwia stary i nowy runtime | Błąd migracji blokuje wdrożenie; rollback nie zakłada cofnięcia destrukcyjnej zmiany |
| Integracja | Konkretna prognoza/anomalia/risk jest widoczna w RetailOps | Stary/replayed wynik nie nadpisuje nowszego |

NetworkPolicy uznaj za sprawdzoną dopiero po rzeczywistych próbach połączeń allow/deny oraz potwierdzeniu aktywnego CNI. Sama obecność YAML nie wystarcza.

## Artefakty i Definition of Done

Chart, values local/AWS, overlay Compose, definicja kind/CNI, adapter Kustomize RetailOps, dokument zasobów, wyniki instalacji i testów sieci/probes, `/version`, zapis update/rollback oraz cleanup. Czyste uruchomienie nie wymaga ręcznego poprawiania manifestów. Odtworzony release jest potwierdzony smoke i kompletem wersji; nie zakładaj, że nieudany upgrade sam zachował całe poprzednie środowisko.

## Gotowy prompt do Codex

```text
Wykonaj etap 14: produkcyjny kształt obrazu AI, Helm i powtarzalny kind, zachowując
RetailOps Kustomize. Najpierw sprawdź realne Compose service names/network/listeners.
Dopisz jawny overlay external network, jeśli nie istnieje. Dodaj non-root/read-only,
probes, zasoby, jobs/CronJobs, oddzielny migration Job i immutable release refs.
Zainstaluj CNI egzekwujące NetworkPolicy, uzgodnij ruch cross-namespace po obu
stronach i wykonaj allow/deny. Bedrock outage nie może blokować klasycznych read
API. Sprawdź worker SIGTERM/ACK, artifact checksum, cold start, idempotentny batch,
czysty deploy i spójny rollback. Pokaż raporty oraz rzeczywiste komendy. Nie
przepisuj bazowego repo na Helm i nie traktuj samych manifestów jako runtime evidence.
```
