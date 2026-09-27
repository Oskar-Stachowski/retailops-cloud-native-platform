# Etap 12 — Uruchom agenta read-only na Bedrock

**Repozytorium:** RetailOps AI. **Wymagane etapy:** 10 i 11. Wcześniej można budować adaptery i test doubles; zamknięcie wymaga działających, autoryzowanych narzędzi danych i zatwierdzonego indeksu. Kontrakty: [integracja i agent](../kontrakty/integracja-agent.md), [API ML i lifecycle](../kontrakty/ml-api-lifecycle.md).

## Cel

Retail Operations Analyst odpowiada na ograniczone pytania o sprzedaż, zapas, forecast, anomalie i stockout, łącząc typed tools z cytowaną dokumentacją. Przedstawia rekomendację do oceny człowieka. Nie wykonuje zamówień, zmian cen, workflow ani promocji modeli i nie przedstawia korelacji jako ustalonej przyczyny.

## Kolejność małych PR-ów

1. **Zaimplementuj tożsamość, scope i katalog narzędzi.** Serwer tworzy principal z tokenu usługowego lub zweryfikowanej tożsamości, przecina zakres żądania z jego uprawnieniami i odrzuca nieautoryzowane scope. Model nie nadaje sobie roli. Dodaj `get_sales_summary`, `get_inventory_status`, `get_demand_forecast`, `get_stockout_risk`, `get_detected_anomalies`, `get_live_operations`, `get_model_status`, `search_knowledge`. Każde narzędzie ma Pydantic input/output, ograniczenia dat/liczby wierszy, timeout, redakcję, source refs, freshness i jawny błąd. Nie dodawaj SQL/HTTP/shell/Python/filesystem ani narzędzia piszącego. Odczyt modelu pokazuje wersję wdrożoną, nie tylko aktualny alias w MLflow.
2. **Dodaj adapter providera i wersjonowaną konfigurację.** W kodzie domenowym nie umieszczaj konkretnego model ID. Konfiguracja przypina Bedrock chat model/inference profile, region, parametry generacji i embeddings z etapu 11. Prompty jako pliki: policy, tool selection, hierarchia dowodów, response schema, odmowa/brak dowodów i ograniczone przykłady. Zapisuj checksum promptu i całej konfiguracji. Fake chat/embeddings provider obsługuje sukces, throttle, timeout, błędny JSON, nieprawdziwy cytat i niedozwolone tool call. Poświadczenia AWS pochodzą z workload identity lub lokalnego zatwierdzonego profilu, nigdy z Git.
3. **Zbuduj mały graf LangGraph z twardym budżetem.** Węzły: validate/auth → plan evidence → retrieve/tools → check evidence → synthesize → validate output → persist safe trace. Najwyżej jeden powrót po brakujący fakt i jedna naprawa schematu w pozostałym budżecie. Nie ma otwartej pętli autonomicznego planowania. Stan przechowuje request, principal/scope, intent, trace/correlation IDs, pinned index i release IDs, tool results/freshness, koszty/limity, błędy i zweryfikowaną odpowiedź. Checkpointy są ograniczone retencją i nie zapisują sekretów ani prywatnego toku rozumowania.
4. **Wprowadź walidację dowodów i deterministyczną politykę sugestii.** Każda liczba biznesowa pochodzi z typed tool; wyliczona różnica ma jawny wzór i dwa źródłowe okresy. Twierdzenia o procesie/modelu mają cytat. Do „wdrożono” potrzeba statusu źródła/evidence z etapu 11. Niejednoznaczny mapping lokalizacji, stale inventory, sprzeczne prognozy, cenzurowana sprzedaż lub brak kalibracji ryzyka pojawiają się w limitations; nie generuj ilości replenishment bez zatwierdzonego narzędzia obliczeniowego. Reguła tworzy kandydata sugestii, LLM może go objaśnić. Wynik zawsze ma `requires_human_review=true` i nie wywołuje działania operacyjnego. Persistowanie trace/odpowiedzi/sugestii nie jest uprawnieniem do zapisu w RetailOps.
5. **Dodaj Assistant API i kontrolowane degradacje.** Zaimplementuj dokładne request/response/error contract z dokumentu kontraktowego, odczyt bezpiecznych metadanych trace oraz autoryzację właściciela. Dla wymaganych niedostępnych danych zwróć 424, Bedrock unavailable → 503, przekroczony globalny deadline → 504, rate/budget admission → 429. Odmowa operacji zapisu i brak wystarczających dowodów mogą być poprawną strukturalnie odpowiedzią 200 z właściwym `outcome`; nie są zmyśloną odpowiedzią. Nie degraduj klasycznych ML read APIs z powodu awarii Bedrock.
6. **Ewaluuj graf, retrieval, odpowiedzi, bezpieczeństwo i koszt.** Użyj wersjonowanych 30–50 pytań z etapu 11 oraz fixture typed tools. Mierz dobór narzędzi/argumentów, zbędne wywołania, schema pass, citation coverage/correctness, numeric faithfulness, groundedness, poprawność odmowy, action policy, latency, tokens i estimated cost. Podaj liczniki i mianowniki. LLM-as-judge może uzupełnić, ale nie zastępuje deterministycznych testów. Zmiana promptu, grafu, tool schema, chat/embedding model, retrieval lub response schema tworzy nową wersję ocenianej konfiguracji.
7. **Wykonaj ograniczony rzeczywisty smoke Bedrock.** Po przejściu offline gates zweryfikuj dostępność wybranego modelu/regionu, wymagane IAM i limity według aktualnej dokumentacji podczas implementacji. Uruchom niewielki, wcześniej ustalony zestaw pytań/embeddings, np. 5–10 przypadków i jawny limit wydatku z konfiguracji. Zapisz rzeczywisty model/profile, region, czas, tokeny/koszt, cytaty i wynik walidacji. Test real nie zastępuje pełnego golden set. Jeśli brak dostępu AWS, oznacz tę bramkę `blocked/not_run`; nie zamykaj etapu twierdzeniem, że stub potwierdził działanie Bedrock. Szerszy cloud showcase należy do etapu 16.

## Kontrole i testy negatywne

- Rzeczywista sugestia wytworzona przez politykę i agenta jest utrwalana wraz z outbox, publikowana na intelligence.v2 i widoczna przez projekcję/read API/UI RetailOps z12/10. Retry daje jeden efekt; sugestia nadal wymaga człowieka i niczego operacyjnie nie wykonuje. To test rzeczywistego producenta, zastępujący fixture używane do odbioru samej projekcji w10.
- Pytanie o aktualną prognozę, ryzyko, brak anomalii i cross-signal investigation ma właściwe narzędzia, scope, unit, as-of, model/release/index IDs i dowody.
- Prompt injection w pytaniu oraz chunku, prośba o sekret, SQL/shell, zmianę ceny, wysłanie zamówienia czy promocję modelu nie uruchamia zabronionych narzędzi. Nie wolno traktować rekomendacji modelu jako autoryzacji użytkownika.
- Podmiana tenant/store, roli w treści pytania, cudzego `conversation_id`, `trace_id` i zawartości cache nie daje obcych danych; trace endpoint również autoryzuje odczyt.
- Narzędzie nieistniejące, błędne argumenty, zbyt szeroki okres, nadmiar wyników i kolejne pętle nie obchodzą budżetu. Jedna naprawa outputu nie resetuje czasu/tokenów.
- Stare inventory, source unavailable, model unapproved/missing, zmiana aliasu, sprzeczne źródła i nieaktualny indeks dają kontrolowany wynik. Model musi pozostać przypięty do release'u; agent nie wybiera przypadkowego artefaktu.
- Zmyślony `source_ref`, cytat do niepobranej sekcji i liczba różna od tool result blokują twierdzenie; nieudana naprawa kończy się kontrolowanym błędem.
- Throttling/transient Bedrock dopuszcza ograniczony backoff z jitter i circuit breaker. Błędy auth/schema nie powodują bezsensownych retry. Cache uwzględnia principal/scope, wersje release/index/prompt i freshness; nie przechowuje prywatnych wyników pod wspólnym kluczem.

## Artefakty i Definition of Done

- Wersjonowane prompty, graf, provider adapters i tool schemas; jeden manifest agent release spinający wszystkie wersje oraz golden set.
- OpenAPI/examples, raport ewaluacji offline i bounded real Bedrock smoke, raport ograniczeń, opis roli/auth, limity i runbook degradacji.
- Evidence rzeczywistej ścieżki rekomendacji: odpowiedź/polityka → trwała sugestia/outbox → v2 → read API/UI RetailOps; zgodne ID, lineage i brak powielenia po retry.
- Bezpieczny ślad pokazujący węzły, narzędzia, source refs, latency/token/cost i decyzję walidatora. Brak ukrytego chain-of-thought w API/logach.
- DoD: wszystkie krytyczne negatywne testy autoryzacji i agency przechodzą; numeryczne odpowiedzi i cytaty mają dowody; graf kończy się w budżecie; real Bedrock smoke potwierdza integrację; klasyczne ML działa przy awarii LLM.

Proponowane interfejsy do implementacji: `make agent-evaluate PROVIDER=fake`, `make agent-security-test`, `make bedrock-smoke`. Dla smoke jawnie podaj config ID i limit kosztu; nie uruchamiaj nieograniczonej ewaluacji chmurowej.

## Prompt do Codex

```text
Zrealizuj etap 12 po zamknięciu 10 i 11. Najpierw skonfiguruj principal/scope,
typed read-only tools, fake provider i skończony graf LangGraph. Przestrzegaj
kontrakty/integracja-agent.md i ML API lifecycle. Wersjonuj prompty i cały agent
release, przypnij indeks i model, waliduj cytaty/liczby oraz limity. Nie dodawaj
operacyjnych zapisów ani dowolnego SQL/HTTP/shell. Przetestuj injection, cudzy
scope/trace, brak/stare dane, awarie i błędne outputy. Podłącz rzeczywiste sugestie
do outbox/v2 i projekcji10; zweryfikuj read API/UI oraz deduplikację. Następnie wykonaj mały
rzeczywisty Bedrock smoke z określonym budżetem. Zapisz raporty z rozróżnieniem
fake, real i not_run, runbook oraz znane ograniczenia. Nie deklaruj wdrożenia
funkcji na podstawie dokumentu oznaczonego specified.
```
