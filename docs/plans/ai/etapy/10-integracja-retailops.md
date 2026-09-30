# Etap 10 — Połącz REST, zdarzenia i wyniki w RetailOps

**Repozytoria:** RetailOps i RetailOps AI. **Wymagane etapy:** 07 i 08. Przygotowanie kontraktów może rozpocząć się wcześniej; odbiór obejmuje działający forecast, anomalie i ryzyko. Zasady obowiązujące: [kontrakt integracji i agenta](../kontrakty/integracja-agent.md), [czas i dane](../kontrakty/dane-i-czas.md), [API ML](../kontrakty/ml-api-lifecycle.md).

## Cel i stan wejściowy

Udostępnić wyniki AI w istniejącym interfejsie RetailOps, z pełnym pochodzeniem i bez podwójnego liczenia faktów. Zrealizować trzy tryby: niezmienny snapshot z etapu 03, ograniczone odczyty REST oraz strumień zdarzeń. Pierwszego działającego forecastingu nie uzależniamy od ukończenia strumienia.

W tym etapie pełne E2E wykorzystuje rzeczywiste wyniki trzech wdrożonych ścieżek ML. **Projekcję sugestii testujemy na jawnym, poprawnym kontraktowo fixture**, ponieważ producent rekomendacji powstaje w12. Fixture nie jest dowodem działania agenta. Etap12 musi później potwierdzić rzeczywistą ścieżkę sugestia → outbox/v2 → RetailOps API/UI.

Przed kodowaniem sprawdź aktualne OpenAPI, obsługiwane typy zdarzeń, granicę trwałości ACK/DLQ oraz projekcje do domenowych read models. Wzrost metryki live nie jest dowodem integracji wyników AI. Ustal semantykę istniejących `/forecasts` i `/inventory-risks`; nie utożsamiaj okresowej prognozy lub heurystyki demo z nowym modelem dziennym i prawdopodobieństwem. Wykorzystaj poprawną istniejącą implementację, a do backlogu dodaj wyłącznie potwierdzone braki.

## Kolejność małych PR-ów

1. **Przypnij kontrakt źródła i dodaj v2.** OPS-07 uzgodnił legacy v1 w `services/api/app/contracts/retailops-realtime-events.v1.contract.json`, `data/generator/realtime.py`, consumerze i topic-init, z wykonywalnym JSON Schema. Zweryfikuj zgodność na nowych commitach obu repo. Zgodnie z ADR-09 zachowaj legacy v1 i wprowadź oddzielny `retailops.intelligence.v2` dla bogatych wyników AI. Nie zmieniaj znaczenia starych pól ani nie traktuj legacy v1 jako odbioru projektora v2.
2. **Dodaj rzeczywisty, typowany klient REST i niezbędne rozszerzenia upstream.** Użyj faktycznych nazw filtrów z kontraktu, domyślnego limitu 50 i maksymalnego 100. Obsłuż puste i ostatnie strony, walidację, sortowanie, timeout, ograniczone retry bezpiecznych GET, circuit breaker i trace headers. W źródłowym `/sales` brakuje `store_id`, `order_id`, `ingested_at`; sama zmiana filtrów nie odtwarza pełnego ziarna. Zaprojektuj kompatybilną projekcję eksportową v2 lub dedykowany wersjonowany eksport, który dostarcza identyfikatory sklepu, zamówienia, wersji i dostępności. Pierwszy import plikowy pozostaje działającą ścieżką. Odróżnij świeżość biznesową od chwili pobrania HTTP.
3. **Zdefiniuj spójny snapshot REST i przekazanie do replay.** Ustal niezmienny `snapshot_id` i wersje rekordów oraz dokładny wektor granicznych offsetów partycji. Eksport nie może zależeć od zmieniającego się `total` przy offset pagination. Jeśli źródło nie zapewnia snapshot isolation/historycznych wersji, zwróć jawny brak wsparcia; nie reklamuj zwykłego odczytu stron jako snapshotu. Wsparcie wymaga utrwalonego eksportu lub protokołu z wysokim watermarkiem i wersjami. Skopiuj do manifestu offsety, included event IDs/natural keys i zakres danych. Uruchom replay od pierwszego nieobjętego offsetu, zachowując deduplikację faktów i obsługę spóźnionych korekt.
4. **Rozszerz trwałe przetwarzanie na domenowe projekcje obu repo.** Obecny runner legacy v1 ma atomowe live metrics, fail-stop bez ACK i trwałą raw kwarantannę PostgreSQL z [runbookiem odtwarzania](../../../runbooks/realtime-recovery.md). Wykorzystaj tę granicę dla v2 i rozszerz ją o domenowe inbox/idempotency, zmianę agregatu/projekcji i outbox w jednej transakcji. Automatyczne ACK pozostaje wyłączone. Przy uszkodzonym JSON zachowaj raw i pozycję przed ACK; przy niedostępnej bazie/kwarantannie nie pomijaj luki partycji. Publisher outbox może powtórzyć wysyłkę, dlatego odbiorca również deduplikuje. Odbiór obecnych metryk nie zastępuje cross-repo E2E wyników AI.
5. **Dodaj projekcje wyników AI i adaptery semantyczne.** W RetailOps osobny projektor utrwala forecast, anomaly, modelowy stockout risk i sugestię wymagającą człowieka. Zachowaj `origin`, wersję modelu, run/dataset IDs, moment prognozy, ziarno, jednostkę, świeżość i identyfikator oryginalnego wyniku. Legacy heurystyka oraz AI probability są różnymi polami/zasobami. Rozszerz read API lub dodaj wersjonowaną projekcję AI. Agregacja do starszego `/forecasts` wymaga jawnego okresu, sumy i jednostki; nie wolno upychać dziennej prognozy sklepu w pole oznaczające całą firmę. Starszy replay pozostaje historią i nie nadpisuje nowszej aktywnej prognozy.
6. **Podłącz istniejący frontend i połączenie usług.** Uzupełnij obecne widoki RetailOps o prognozę, anomalie, ryzyko, sugestie, link do lineage i status świeżości. Oddziel dane demo, heurystykę i modele AI. UI wyświetla źródło i ograniczenia, a akcję operacyjną wykonuje człowiek w istniejącym workflow. Nie twórz drugiego dashboardu. Przygotuj overlay Compose: istniejące usługi to `api`, `db`, `redpanda`; aliasy `retailops-api` i external network są nową konfiguracją. AI ma osobną bazę, korzysta z tego samego brokera i poprawnego advertised listener. Cleanup usuwa tylko zasoby AI. Polityki cross-namespace zostaną sprawdzone w etapie 14.
7. **Zamknij kompatybilność, auth i runbook.** Wprowadź tokeny usługowe poza Git, ograniczone origins, prywatną komunikację oraz principal ustalany na serwerze. Lokalny demo user RetailOps nie jest zweryfikowaną tożsamością użytkownika AI. Dostęp do danych, runów i trace’ów sprawdzaj po stronie API. Zapisz procedurę backfill/replay, zatrzymania partycji, naprawy i ponownego odczytu DLQ oraz pełnego resync z nowego snapshotu.

## Kontrole i testy negatywne

- REST: porównanie fixture z faktycznym OpenAPI RetailOps; 0, 1, 100 i ponad 100 rekordów; nieznane opcjonalne pola; niewłaściwy filtr; timeout; 429/503; nieaktualne źródło; brak pól ziarna. Próba eksportu podczas równoczesnych insert/update nie gubi ani nie powiela danych.
- Kontrakty: wszystkie producenci i konsumenci zgadzają się co do topic/type/version; zły major, nieznany type, niezgodne topic, brak topic i błędny payload trafiają do kontrolowanej ścieżki. Legacy v1 nadal działa na dawnym seedzie.
- Przekazanie: snapshot plus nakładający się replay daje te same fakty co jeden pełny przebieg; granice partycji, opóźnione zdarzenia, inny envelope ID dla tego samego biznesowego faktu i korekty nie duplikują sum. Aktualizacja wersji faktu zastępuje jego wkład zgodnie z polityką curation.
- Awaria: błąd DB przed commit → bez ACK; crash po commit i przed ACK → replay bez drugiego efektu; poison message przy niedostępnej DLQ → bez utraty; po poprawieniu zależności partycja wznawia od właściwego miejsca. Przy przetwarzaniu równoległym nie wolno przeskoczyć luki offsetów.
- Projekcja: test czyta konkretny `forecast_id`/`risk_id` przez read API RetailOps oraz sprawdza źródło/model/grain. Ten sam event dwa razy daje jeden efekt, starszy wynik nie nadpisuje nowszego. Heurystyczny risk nie jest przedstawiany jako prawdopodobieństwo ML.
- Uprawnienia: zmiana `user_id` w query, podmiana `store_id`, dostęp do cudzego runu i wywołanie endpointu administracyjnego z przeglądarki nie zwiększają praw principal. Brak poświadczeń nie dziedziczy demo admina.
- Dostępność: przerwa Bedrock nie zatrzymuje odczytu modeli; przerwa REST zwraca określony brak danych; niedostępny broker jest widoczny jako degradacja i backlog, bez utraty outbox.

Profil `ai-smoke` (30 dni) jest tylko fixture dla schema/import/replay. Temporalną integrację prognoz i ryzyka wykonaj na `ai-temporal-smoke` (102 dni), zgodnie z [profilami i bramkami](../kontrakty/profile-i-bramki.md). Nie interpretuj wyniku smoke jako dowodu jakości ML.

## Artefakty i Definition of Done

- Zatwierdzona mapa REST, OpenAPI/JSON Schema i tablica kompatybilności v1/v2; plik overlay Compose i konfiguracja topic-init.
- Protokół snapshot/replay z przykładowym manifestem; migracje inbox/outbox/DLQ/read models; projekcje trzech wyników ML i sugestii.
- Powtarzalny raport bounded E2E z sumami przed/po replay, offsetami, kontrolowanymi awariami oraz odpowiedzią read API i widokiem UI.
- Runbook odtwarzania i diagram własności danych; dotychczasowy seed/API test suite nadal przechodzi.
- DoD: istnieje trwały odczytywalny wynik w RetailOps i brak utraty/podwojenia efektu przy testowanych awariach. Samo przyjęcie eventu, log lub licznik nie zamykają etapu.

Proponowany docelowy interfejs weryfikacyjny (do zaimplementowania i opisania w README, nie istniejąca obecnie komenda): `make integration-replay-test` oraz `make integration-failure-test`. Raportuj dokładnie, co wykonano i na których commitach obu repozytoriów.

## Prompt do Codex

```text
Wykonaj etap 10 zgodnie z tym plikiem i kontrakty/integracja-agent.md. Najpierw
przypnij oba commity i pokaż różnicę między istniejącym API/consumerem a wymaganiami.
Pracuj w małych PR-ach w odpowiednim repozytorium. Zachowaj legacy v1 i demo; nową
semantykę AI realizuj przez intelligence.v2 i jawne projekcje. Nie używaj wspólnej
bazy źródłowej ani fallbacku do danych symulacyjnych. Napraw trwałość inbox/outbox,
ACK i DLQ, w tym invalid JSON, crash i lukę partycji. Zweryfikuj snapshot/replay,
konkretny wynik w read API RetailOps, UI i uprawnienia principal. Użyj fixture
30-dniowej tylko dla schematów, a 102-dniowej dla temporalnego E2E. Rekomendacje
sprawdź na oznaczonym fixture; rzeczywisty producent i pełna ścieżka do UI w12. Nie uznawaj
wzrostu metryk za dowód projekcji. Zapisz evidence, rollback i pozostałe ograniczenia.
```
