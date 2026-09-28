# Plan rozbudowy RetailOps AI

**Status: etap 01 odebrany; następny zakres DATA-01 w etapie 02. Aktualizacja: 28.09.2026.**
[Audyt na `cbf28b2`](../../evidence/ai/00/README.md) ustala zmierzony stan wyjściowy.
[Fundament AI](../../evidence/ai/01/README.md) obejmuje osobne lokalne repo,
pakiet, HTTP, PostgreSQL/pgvector, oddzielny MLflow, Compose i wykonywalne
kontrakty danych/run/tool z walidacją offline oraz lokalne poświadczenia i scope API.
Required CI PR i push na main obu repozytoriów ma success; ochrona main pozostaje aktywna.
Następną implementacją jest DATA-01 w etapie 02, a równolegle można rozpocząć RAG 11.
[Backlog](backlog.md) podaje pierwszy mały PR 02 i granice równoległych strumieni.
Etapy 02–17 opisują rozwój do wdrożenia; nie potwierdzają
istnienia planowanych komponentów ani zatwierdzenia kosztów lub infrastruktury.

Istniejący RetailOps ma [lokalną ocenę RF](../../evidence/ml/fixed-origin-rf-2026-09-27/README.md) i politykę decyzji; ostatni wynik to `rejected`. Przy rozpoczęciu rozbudowy AI wykorzystaj kontrakt cech, protokół czasowy i te dowody. Pełny serwis AI i etap 07 dotyczący anomalii pozostają osobnym zakresem.

Czytaj kolejno tę mapę, [architekturę](architektura.md) i plik właściwego [etapu](etapy/00-audyt.md). Wspólne wymagania opisują [dane i czas](kontrakty/dane-i-czas.md), [profile i bramki](kontrakty/profile-i-bramki.md), [ML/API](kontrakty/ml-api-lifecycle.md) oraz [integracja i agent](kontrakty/integracja-agent.md). [Runbook docelowy](runbooki/operacje-i-awarie.md) i [szablony kart](szablony/karty-i-evidence.md) są materiałami pomocniczymi. [Rejestr zależności](etapy.json) zawiera tę samą numerację 00–17.

## Cel i podział pracy

**RetailOps** pozostaje właścicielem danych operacyjnych, generatora, API i interfejsu sklepowego. **RetailOps AI Intelligence** ma osobne repozytorium z pakietem, HTTP i lokalnym stosem PostgreSQL/MLflow. Docelowy serwis będzie odpowiedzialny za przetwarzanie danych, modele, predykcje, RAG i agenta. Repozytoria komunikują się przez wersjonowane pliki, API i zdarzenia; mają oddzielne bazy danych.

Efektem końcowym będzie system, który prognozuje sprzedaż, wykrywa anomalie, ocenia ryzyko braku zapasu oraz wyjaśnia wyniki przy pomocy agenta korzystającego z danych i cytowanych dokumentów. Całość ma mieć powtarzalne eksperymenty, kontrolowane wdrożenia, monitoring, rollback i dowody działania.

## Mapa kroków

| Krok | Co zrobić | Główny rezultat | Gdzie |
|---|---|---|---|
| [00](etapy/00-audyt.md) | Stan wyjściowy na `cbf28b2`: [raport](../../evidence/ai/00/README.md). | Pomiary, istniejące funkcje i [backlog](backlog.md). | RetailOps; inwentaryzacja dostępności AI |
| [01](etapy/01-fundament-projektu.md) | Ustal granice systemu, kontrakty i uruchom szkielet AI. | Działająca aplikacja bazowa, konfiguracja, lokalne zależności i podstawowe CI. | Oba repo |
| [02](etapy/02-dane-sprzedazowe.md) | Napraw generator i uporządkuj dane sprzedaży, cen, promocji i lokalizacji. | Spójny panel dzienny, poprawna chronologia i rozdzielenie danych od prawdy symulatora. | RetailOps |
| [03](etapy/03-snapshot-curated.md) | Zbuduj eksport, importer i oczyszczoną warstwę danych. | Niezmienny snapshot z identyfikatorami, kontrolą integralności i bramkami jakości. | Oba repo |
| [04](etapy/04-forecasting.md) | Zbuduj baseline i model forecastingu z poprawną oceną czasową. | Prognozy obserwowanej sprzedaży bez leakage, także dla dni z zerową sprzedażą. | AI |
| [05](etapy/05-mlflow-serving.md) | Połącz eksperymenty, rejestr modeli, batch inference i API. | Pierwsza działająca ścieżka: snapshot → model → MLflow → zapisana prognoza → API. | AI |
| [06](etapy/06-inventory-ledger.md) | Zbuduj spójny model zapasu, dostaw i realizacji sprzedaży. | Ledger uzgadnialny ze sprzedażą i dostawami oraz wiarygodne epizody stockout. | RetailOps |
| [07](etapy/07-anomalie-dq.md) | Dodaj kontrolowane anomalie i błędy danych oraz ich detekcję. | Oddzielne etykiety, oczyszczanie danych, baseline i oceniony detektor anomalii. | Oba repo |
| [08](etapy/08-stockout-risk.md) | Zbuduj model ryzyka braku zapasu. | Skalibrowane prawdopodobieństwa, uzasadnione progi i bezpieczne czasowo cechy. | AI |
| [09](etapy/09-tensorflow-robustness.md) | Dodaj TensorFlow challenger i zakończ porównanie modeli. | Rzetelna ewaluacja trzech zastosowań, odporności i ograniczeń modeli. | AI |
| [10](etapy/10-integracja-retailops.md) | Uzgodnij REST i zdarzenia, a następnie pokaż wyniki AI w RetailOps. | Kontrakty, trwałe przetwarzanie, deduplikacja oraz rzeczywiste wyniki dostępne w API/UI. | Oba repo |
| [11](etapy/11-rag.md) | Przygotuj zatwierdzony korpus wiedzy i RAG. | Wersjonowany indeks pgvector, cytowania i oceniona jakość wyszukiwania. | AI |
| [12](etapy/12-agent-bedrock.md) | Zbuduj agenta read-only z LangGraph i Amazon Bedrock. | Odpowiedzi oparte na narzędziach i dokumentach, z limitami, świeżością danych i oceną jakości. | AI |
| [13](etapy/13-monitoring-security.md) | Zakończ monitoring, drift, zabezpieczenia i obsługę awarii. | Metryki, dashboardy, alerty, ślady wykonania i przećwiczone procedury naprawcze. | Oba repo |
| [14](etapy/14-helm-kind.md) | Zapakuj AI do Helm i uruchom cały system na kind. | Powtarzalne lokalne wdrożenie Kubernetes z migracjami, politykami sieciowymi i health checks. | Oba repo |
| [15](etapy/15-cicd-gitops.md) | Zamknij proces CI/CD i wdrażanie przez Argo CD. | Wersjonowany release, wymagane kontrole, synchronizacja i sprawdzony rollback. | AI |
| [16](etapy/16-aws.md) | Przygotuj Terraform i wykonaj kontrolowany pokaz AWS. | **16A:** zweryfikowany projekt infrastruktury. **16B:** dowody działania wybranego wariantu i sprzątnięcia zasobów. | Oba repo |
| [17](etapy/17-odbior-portfolio.md) | Przeprowadź odbiór całości i przygotuj portfolio. | Odtwarzalne demo, dowody wyników, aktualna dokumentacja i wydanie v1. | Oba repo |

## Kolejność i zależności

Domyślnie realizuj kroki według numeracji. **Nie trzeba kończyć całego systemu danych dla trzech modeli, żeby uruchomić pierwszą poprawną prognozę.** Kroki 00–05 tworzą pierwszy kompletny rezultat. W tej wersji pomijamy cechy zapasu, które nie spełniają jeszcze kontraktu danych; nie przedstawiamy jej jako modelu niezaspokojonego popytu ani ryzyka stockout.

Po kroku 06 zmienia się symulator i powstaje nowa wersja danych. Powtórz import, budowę cech oraz ocenę modeli zależnych od tych danych. Nie porównuj modeli uczonych na różnych snapshotach tak, jakby uczestniczyły w jednym eksperymencie.

Możliwa praca równoległa:

- **06** można rozpocząć po **03**, równolegle z pierwszym forecastingiem.
- **07 i 08** można rozwijać równolegle po zakończeniu ich zależności; każdy ma własną bramkę danych i ewaluacji.
- **11** można rozpocząć po **01**, a później uzupełniać korpus o zatwierdzone karty i wyniki.
- **09 i 10** można rozwijać równolegle po **07–08**.
- Projektowanie **16A** może rozpocząć się wcześniej, kiedy znane są wymagania infrastruktury; **16B** następuje po lokalnym wdrożeniu i kontrolach.

CI, bezpieczeństwo, metryki i dokumentowanie dowodów zaczynają się w kroku 01 i rozwijają przy każdej funkcji. Późniejsze etapy oznaczają ich pełne spięcie i odbiór.

## Trzy punkty odbioru

| Punkt | Kiedy | Co musi działać |
|---|---|---|
| **K1 — pierwszy działający system AI** | Po 00–05 | Poprawny snapshot, forecasting, MLflow, zapis wyników i odczyt API. |
| **K2 — pełne lokalne portfolio** | Po 00–15 oraz 16A | Trzy zastosowania ML, uruchomiony TensorFlow challenger, REST/zdarzenia, RAG i agent, monitoring, kind/Helm/Argo CD, rollback oraz walidacja Terraform. Wymagany także ograniczony rzeczywisty test Bedrock. |
| **K3 — portfolio v1 z AWS** | Po 16B i 17 | K2 oraz udokumentowany pokaz AWS, kontrola kosztów, cleanup i końcowy odbiór. |

TensorFlow ma zostać uczciwie porównany; nie musi wygrać. Pokaz AWS może używać czasowego EKS/RDS albo jawnie opisanego wariantu lokalnego połączonego z usługami AWS. Zakres faktycznie wdrożony musi odpowiadać opisowi w portfolio. Stałe kosztowne środowisko chmurowe nie jest wymagane.

## Jak wykonywać jeden etap

1. Sprawdź jego zależności, aktualny kod i zakres już objęty działającą implementacją. Etap 00 służy tej weryfikacji.
2. Wykonuj małe, spójne zmiany zgodnie z [wspólną instrukcją](prompty/00-zasady-wykonania.md), zachowując działające demo.
3. Przed implementacją uzgodnij kontrakty, wersje i kryteria odbioru. Wartości planowanych progów nie są wynikami pomiarów ani automatycznie obowiązującą polityką obecnego RetailOps.
4. Sprawdzaj rzeczywiste zachowanie i wymagane przypadki błędów. Nazwy nowych komend i endpointów w planie są interfejsami do zaimplementowania.
5. Zapisuj małe, odtwarzalne dowody z wersją kodu, danych i środowiska. Usuwaj z aktywnego planu wykonany zakres i rozwiązane ustalenia; nie dopisuj do nich statusu „zrobione”. Aktualny opis działającego systemu utrzymuj w dokumentacji właściwej funkcji.

Mapa określa kolejność, kontrakty znaczenie danych i warunków jakości, a etapy wykonanie i odbiór. Sprzeczność wymaga jawnego rozstrzygnięcia i aktualizacji powiązanych dokumentów. AI korzysta z wersjonowanych danych, API i zdarzeń RetailOps; ma własną bazę. Nie kopiuje generatora ani frontendu.
