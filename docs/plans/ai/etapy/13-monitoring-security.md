# 13 — Zamknij monitoring, drift i bezpieczeństwo

**Repozytoria:** RetailOps + AI. **Zależności zakończenia:** 09 i 12. **Status dokumentu:** instrukcja wykonania; nie dowód gotowej implementacji.

## Cel i granica etapu

Udowodnić, że problemy aplikacji, danych, modeli, zdarzeń i agenta są wykrywane, ograniczane i możliwe do odtworzenia. Logowanie, autoryzację, limity, testy i podstawowe CI wdrażamy od etapu 01 i rozwijamy w każdym PR. Etap 13 zamyka ich kompletność oraz ćwiczenia awarii; nie jest pierwszym momentem dodania bezpieczeństwa.

Przeczytaj [architekturę](../architektura.md), [kontrakt lifecycle](../kontrakty/ml-api-lifecycle.md), [integrację i agenta](../kontrakty/integracja-agent.md) i [runbook](../runbooki/operacje-i-awarie.md).

## Kolejność małych PR-ów

1. **Inwentaryzacja i model zagrożeń.** Zmapuj wejścia niezaufane: HTTP, zdarzenia, dokumenty RAG, artefakty modeli, zależności/CI. Przypisz właściciela, kontrolę, test negatywny oraz pozostałe ograniczenie. RetailOps ma granicę demo auth; nie traktuj jej jak gotowego login/JWT. Tożsamość pochodzi z serwerowego adaptera uwierzytelnienia, nie z `user_id` query ani roli wymyślonej przez LLM. Uprawnienia narzędzi są przecięciem zakresu principal i żądanego zakresu. Chroń także odczyt runów, trace'ów, MLflow i endpointów administracyjnych. Rozdziel local demo i wystawione środowisko.
2. **Metryki i ślady.** Ujednolić strukturalne logi JSON oraz OpenTelemetry na granicach API → narzędzie → RetailOps/DB/RAG/Bedrock. Dodaj correlation/trace/run ID do logów i odpowiedzi, bez umieszczania ich w etykietach Prometheus. Rejestruj czas, wynik, kontrolowany kod błędu, release/model/config/index. Nie zapisuj sekretów, connection strings, surowych promptów, pełnych dokumentów, embeddings ani ukrytego rozumowania. Opisz retencję i redakcję w konfiguracji oraz testach.
3. **Pięć dashboardów i alerty.** Przygotuj service health, pipeline/data/events, ML, agent/RAG i release. Każdy panel wskazuje właściwe źródło, jednostkę i okno pomiaru. Wersje modeli i release'u muszą odpowiadać runtime. Alert ma ownera, poziom, warunek, opóźnienie, link do runbooka oraz warunek wygaszenia. Sprawdź również działanie alertu, gdy nie ma próbek metryki albo job nigdy się nie powiódł.
4. **Drift i opóźnione outcomes.** Dla trzech modeli zbieraj data/feature/prediction drift, a po dojrzeniu etykiet performance, bias i kalibrację. Zapisuj liczebność, kompletność okna, referencję, definicję metryki i segmenty. `not_evaluable` nie oznacza sukcesu. Ostrzeżenie rozpoczyna analizę; nie uruchamia automatycznie treningu ani promocji. Nie podnoś progów tylko po to, by wyciszyć alert. Wersjonuj parametry monitoringu; rozdziel regresję retrieval od regresji odpowiedzi agenta.
5. **Kontrole aplikacyjne i supply chain.** Egzekwuj walidację, limity rozmiaru requestu, rate/concurrency limit, timeout i budżet tokenów/narzędzi. Parametryzuj SQL, ogranicz CORS, sanitizuj błędy i wyłącz debug poza dev. Skanuj sekrety, zależności, kontenery oraz IaC; publikuj SBOM i jawny wynik skanu. Wyjątek od blokującej podatności wymaga udokumentowanego ryzyka, ownera i terminu, nie milczącego wyłączenia gate. Ładuj tylko zaufane artefakty o sprawdzonej sumie i przypiętej wersji.
6. **Ćwiczenia awarii i odzyskiwania.** Zrealizuj przypadki poniżej na syntetycznych danych. Odtwórz normalny stan i zachowaj zwięzły dowód. Uzupełnij runbook datą i rzeczywistymi komendami. Skan i konfiguracja nie zastępują sprawdzenia zachowania runtime.

## Minimalny zakres sygnałów

| Grupa | Mierzymy | Reguły |
|---|---|---|
| Aplikacja | request count/error, p95, dependency outcome, pool DB, job success/duration | Route jako szablon; bez ścieżek z ID |
| Dane/zdarzenia | wiek snapshotu, błędy kontraktu, lag, DLQ, retry, outbox age | Brak `product_id`, `store_id`, `event_id`, `dataset_id` jako nieograniczonych etykiet |
| ML | model/version, volume, freshness, failed/skipped rows, drift, metryki na dojrzałych labelach | Szczegółowe segmenty i lineage w raporcie/DB |
| Agent/RAG | outcome, tool/error/latency, tokens, koszt szacowany, citations, index freshness | Bez pytań użytkownika i dokument paths w etykietach |
| Release | obraz, model, config, index, schema i zdrowie wdrożenia | Niewielka liczba info metrics; historia w evidence |

Początkowe cele pomiarowe: p95 read API <500 ms bez cold start, standardowe zapytanie agenta <15 s, dzienne wyniki i zatwierdzony indeks odświeżone w 24 h. Dla streamu ustaw jawne okno świeżości. To cele dev/showcase: wynik raportuj wraz z hardware, wolumenem, obciążeniem i długością próby. Nie wyprowadzaj dostępności 99,5% z kilkuminutowego smoke.

## Testy akceptacyjne, w tym awarie

- Niedostępny model lub niezgodny checksum uniemożliwiają gotowość wymaganej ścieżki ML; nie przełączają jej po cichu na inny model. Awaria Bedrock degraduje asystenta, a odczyty ML pozostają dostępne.
- Stare inventory/source/index są widoczne w odpowiedzi i alarmach; brak danych nie jest zerem ani świeżą prognozą.
- Niedostępna baza, broker lub DLQ nie powodują utraty eventów, ACK ponad luką ani duplikacji projekcji po retry. Odpowiedni alert wskazuje przyczynę i odzyskanie.
- Złośliwy chunk RAG, niedozwolony tool i próba odczytu cudzego runu nie przechodzą. Niepoprawny JSON odpowiedzi i przekroczenie limitów mają kontrolowany wynik bez nieskończonej pętli.
- Po awarii model loading, injection oraz brokera istnieją: wynik negatywny, sygnał wykrycia, decyzja containment, recovery i kontrola integralności.
- Skan logów/testowych trace'ów nie ujawnia syntetycznych sekretów testowych. Testy autoryzacji obejmują zarówno dozwolone, jak i zabronione zasoby.

## Artefakty i Definition of Done

Powstają dashboard JSON, reguły alertów, konfiguracja OTel/retencji/redakcji, threat model, raport skanów/SBOM, drift reports, zanonimizowany trace i co najmniej trzy ćwiczenia awarii. Każdy wynik ma commit, konfigurację, czas, komendę i ograniczenia według [szablonów](../szablony/karty-i-evidence.md).

Etap jest zamknięty, gdy wszystkie grupy sygnałów mają dowód runtime, alerty wykryły rzeczywiste kontrolowane awarie, podstawowe granice dostępu przeszły testy negatywne, odzyskano spójny stan, a README nie obiecuje nieprzetestowanych właściwości. Kontrole podów, NetworkPolicy i cloud IAM zostają dodatkowo zweryfikowane w 14 i 16.

## Gotowy prompt do Codex

```text
Zrealizuj etap 13 z tego pakietu w małych PR-ach, na bazie istniejących kontroli
z etapów 01–12. Najpierw wskaż luki względem dokumentu, następnie uzupełnij
metryki/logi/OTel, dashboardy, alerty, drift na dojrzałych labelach, autoryzację,
redakcję i skany. RetailOps demo auth nie jest dowodem uwierzytelnienia użytkownika.
Wyćwicz broker/DB/DLQ, brak modelu, stale data, Bedrock outage i prompt injection;
sprawdź niezależność read API ML od Bedrock. Nie dodawaj wysokiej kardynalności do
Prometheus ani sekretów do trace'ów. Zapisz failure i recovery evidence, skoryguj
runbook oraz status implemented wyłącznie dla sprawdzonych funkcji. Nie zmieniaj
modeli lub progów automatycznie w odpowiedzi na drift. Komendy uznaj za istniejące
dopiero po ich implementacji i wykonaniu.
```
