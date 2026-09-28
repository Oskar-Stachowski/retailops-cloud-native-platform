# Gdzie realizować etapy AI i co można robić równolegle

Aktualizacja: **2026-09-28**. To pisemna mapa wykonania oparta na
[rejestrze zależności](etapy.json) i instrukcjach poszczególnych etapów.
[Status projektu](../../STATUS.md) oraz [odbiór RAG 11](../../evidence/ai/11/README.md)
opisują faktycznie dostępne funkcje. Numer etapu nie oznacza jednego repozytorium.

**Cloud-native** oznacza `retailops-cloud-native-platform`: generator, fakty
operacyjne, API i UI RetailOps oraz jego infrastruktura.
**AI-intelligence** oznacza `retailops-ai-intelligence`: importer/curated,
cechy, trening, modele, batch/serving, RAG, agent i infrastruktura usługi AI.
Repo AI nie przejmuje generatora, frontendu ani dostępu do domenowej bazy RetailOps.

## Przypisanie repozytoriów i warunków wejścia

| Etap | Repozytorium i podział pracy | Wymagany poprzednik |
|---|---|---|
| [03 — snapshot/curated](etapy/03-snapshot-curated.md) | **Oba**: cloud-native — Parquet, polityka artefaktów i niezmienny eksport; wspólny kontrakt/fixture; AI-intelligence — importer, curated i walidacja odbioru. | 02 |
| [04 — forecasting](etapy/04-forecasting.md) | **AI-intelligence**: cechy, baseline, RF/HGB, ocena czasowa i artefakty. | 03 |
| [05 — MLflow/batch/API](etapy/05-mlflow-serving.md) | **AI-intelligence**: tracking, registry, worker, zapis predykcji, serving i rollback. | 04 |
| [06 — inventory](etapy/06-inventory-ledger.md) | **Cloud-native**: ledger, dostawy, źródłowe bramki i nowa wersja danych. AI odbiera nowy eksport przez mechanizmy 03 i ponawia zależne oceny 04/05. | 03 |
| [07 — anomalie/DQ](etapy/07-anomalie-dq.md) | **Oba**: cloud-native — scenariusze i oddzielne truth/raw faults; AI-intelligence — curation, detekcja, ocena i lifecycle modelu. | 04, 05 i 06 |
| [08 — stockout](etapy/08-stockout-risk.md) | **AI-intelligence**: labels, cechy, model ryzyka, kalibracja i API na poprawnych danych inventory. | 04, 05 i 06 |
| [09 — TensorFlow/robustness](etapy/09-tensorflow-robustness.md) | **AI-intelligence**: challengery i porównanie trzech zastosowań. | 07 i 08 |
| [10 — integracja](etapy/10-integracja-retailops.md) | **Oba**: AI — wyniki/outbox/publisher; cloud-native — kontrakty, consumer, projekcje/read API/UI; wspólnie auth, replay i E2E. | 07 i 08 |
| [11 — RAG](etapy/11-rag.md) | **AI-intelligence**: korpus obu repo, indeks, retrieval, jakość i administracja. Cloud-native utrzymuje aktualne źródła dokumentacyjne i status. | 01 |
| [12 — agent](etapy/12-agent-bedrock.md) | **AI-intelligence**: narzędzia read-only, graf, Bedrock, odpowiedzi i sugestie. Odbiór obejmuje również dostarczenie sugestii do projekcji/UI RetailOps z 10. | 10 i 11 do pełnego zamknięcia |
| [13 — monitoring/security](etapy/13-monitoring-security.md) | **Oba**: telemetry, drift, dostęp, alarmy i ćwiczenia awarii całej integracji. | 09 i 12 do zamknięcia |
| [14 — Helm/kind](etapy/14-helm-kind.md) | **Oba**: AI — obraz/Helm/jobs; cloud-native — istniejący Kustomize, sieć i integracja; wspólny clean deploy/rollback. | 13 do zamknięcia |
| [15 — CI/CD/GitOps](etapy/15-cicd-gitops.md) | **Głównie AI-intelligence**: release i Argo CD. Cloud-native zachowuje zgodne kontrakty i własne wymagane CI. | 14 |
| [16A — projekt infrastruktury](etapy/16-aws.md) | **Oba**: cloud-native zachowuje foundation/state; AI ma własne zasoby/state, uzgodnione inputs, IAM, walidację i kosztorys. | Przygotowanie po 01, gdy znane są inputs i ownership |
| [16B — pokaz AWS](etapy/16-aws.md) | **Oba**: uzgodniony wariant, rzeczywiste wykonanie, dowody i cleanup. | 15 oraz odebrane 16A |
| [17 — odbiór/portfolio](etapy/17-odbior-portfolio.md) | **Oba**: wspólne demo, końcowy audyt, dokumentacja i spójne wydanie. | Cały 16 |

## Zalecana kolejność od obecnego punktu

1. **Teraz AI 03.4 w AI-intelligence:** typed importer, następnie curated
   i końcowy odbiór rzeczywistego eksportu/importu między repozytoriami.
   Typed Parquet, exporter oraz handoff/fixture 03.1–03.3 mają lokalny odbiór.
   AI 11 jest odebrany i opublikowany w repo AI. Równolegle można przygotować
   interfejsy i test doubles 12; nie zamyka to pełnego agenta.
2. **Po 03:** równolegle 04 w AI-intelligence oraz 06 w cloud-native.
   Po 04 można przejść do 05, nawet jeśli 06 jeszcze trwa. Pierwszy
   forecasting opisuje obserwowaną sprzedaż i pomija niegotowe cechy inventory.
3. **Po 06:** ponowić eksport/import i zależne oceny 04/05 na nowym snapshotcie.
   Gdy 04, 05 i 06 mają zgodne odbiory, rozwijać równolegle **07 i 08**.
4. **Po 07 i 08:** równolegle **09 i 10**. Zmiany modeli w 09 nie powinny
   wstrzymywać integracji 10, która używa przypiętych, odebranych artefaktów
   i uzgodnionych kontraktów.
5. **Po 10 i gotowym indeksie 11:** pełny zakres **12**. Może trwać równolegle
   z pozostałymi pracami 09. Adaptery i test doubles 12 można przygotować
   wcześniej. Rzeczywiste embeddings i jakość wyszukiwania odebrano w 11.
   Odbiór 12 musi dodatkowo sprawdzić odpowiedzi i wykonanie narzędzi;
   smoke nie zastępuje ich golden set ani pełnej bramki integracji 10.
6. **Po 09 i 12:** zamknąć **13**, następnie **14**, potem **15**.
   Logowanie, bezpieczeństwo, CI i podstawowe metryki rozwijamy od początku;
   te późniejsze numery oznaczają pełny odbiór, nie początek dbania o jakość.
7. **16A** można prowadzić jako niezależny strumień wcześniej, po uzgodnieniu
   wymagań infrastruktury. **16B** realizujemy po 15 i 16A, a **17** po 16B.
   Projektowanie infrastruktury nie oznacza uruchomienia zasobów AWS.

## Organizacja równoległej pracy

Każdy strumień ma osobny branch/worktree i PR. Wspólne kontrakty otrzymują
jedną uzgodnioną wersję i fixture, a zmiany po obu stronach osobne commity.
Nie prowadź dwóch strumieni w jednym katalogu roboczym repo AI.
Korpus RAG aktualizuj przez nowy zatwierdzony snapshot; zmiana dokumentacji
na `main` nie zmienia samoczynnie już przypiętego indeksu.

Pierwszy odbiór **K1** wymaga 00–05 i nie czeka na pełny inventory ani agenta.
**K2** obejmuje 00–15, 16A i rzeczywisty ograniczony smoke Bedrock.
**K3** dodaje 16B oraz końcowy odbiór 17.
