# 01 — Architektura, repozytoria i szkielet AI

**Repo:** oba; nowe komponenty w AI. **Zależność:** 00. **Rezultat:** działający fundament lokalny bez deklaracji gotowych modeli.

**Stan bieżący:** osobne repo `retailops-ai-intelligence` zawiera pakiet,
settings, CLI i bazowy HTTP w warstwach api/domain/pipelines/adapters.
Działają PostgreSQL/pgvector dla AI oraz oddzielna baza i rola MLflow, jawne
migracje i lokalny Compose z trwałymi wolumenami.
[Dowody](../../../evidence/ai/01/README.md) obejmują 77 testów i czysty checkout
z rzeczywistymi próbami crash/restart, DB outage/recovery i zachowania artefaktów.
Repo jest na GitHub, main chronione przez required-result, CI bazowego 7d67530
ma success. Commity persistence są lokalne, ich zdalny CI czeka na push.
Cały etap jest `in_progress`; poniżej pozostaje zakres do wykonania.

Przeczytaj [architekturę](../architektura.md) i wspólne kontrakty w `../kontrakty/`. Model danych/ziarno/availability uzgodnij przed implementacją pipeline’ów; pełne zdarzenia zostaną uruchomione w 10.

## Praca w małych PR-ach

6. **Wspólne kontrakty.** Nadaj wersje dataset/feature/label/prediction/run/tool schemas; wzory w tym pakiecie przełóż na wykonywalne modele i fixtures w repo. Zapisz semantykę braków, zer, czasu i source ownership. Event schema inventory jeszcze nie oznacza działającego streamingu.
7. **Rozwój CI i zabezpieczeń.** Rozszerz istniejące lint/type/package/test/docs/contracts i secret scan na nowe komponenty bez pomijania ich ścieżek. Po push nowych commitów odbierz ich zdalne CI z nowym jobem persistence; zachowaj wymaganą ochronę main przez `required-result`. Własne endpointy administracyjne od początku mają granicę dostępu. Sekrety poza Git i logami. Używaj ról o ograniczonym zakresie, nie demo admina RetailOps jako domyślnej tożsamości agenta.
8. **Status i polecenia.** Rozwijaj istniejące `make bootstrap`, `make test` i `make ci-local` wraz z aplikacją. Rozwijaj działające polecenia Compose i smoke wraz z nowymi rolami. Nie dopisuj pustych targetów udających działający trening/deploy. Aktualizuj rejestr etapu i evidence.

## Ustawienia i granice

Konfiguracja docelowa obejmuje APP_ENV, DATABASE_URL, MLFLOW_TRACKING_URI, RETAILOPS_API_URL, KAFKA_BOOTSTRAP_SERVERS, region/model allowlist Bedrock, ścieżki artefaktów i OTEL endpoint. Wartości środowiskowe nie trafiają na sztywno do domeny. `.env.example` zawiera wyłącznie bezpieczne placeholdery.

W fazie K1 wykonanie jest lokalne. Brak źródła RetailOps powoduje kontrolowany błąd importu; brak opcjonalnego LLM — czytelny status degraded. Nie ukrywaj awarii użyciem przypadkowego modelu ani danych syntetycznych, których użytkownik API nie zamówił.

## Kontrole odbioru

- Czysty checkout daje działający import pakietu i powtarzalną instalację z lockfile.
- Compose podnosi API, PostgreSQL i MLflow; restart zachowuje trwałe dane w wymaganych wolumenach.
- Odłączenie DB pogarsza readiness; `/health` nie wykonuje kosztownych testów wszystkich usług.
- Logi mają correlation ID i nie mają haseł/tokenów. `/version` nie ujawnia sekretów.
- CI wykrywa błędny kontrakt i nie pomija nowej ścieżki; docs nie deklarują nieistniejących funkcji.
- Testy provider fakes nie wymagają konta AWS; migracje wykonują się jawnie.

Zapisz ADR-y, listę uruchomionych poleceń i ograniczenia. Etap odblokowuje dane02, RAG11 oraz projektowanie16A po określeniu infrastrukturalnego input contract.

## Prompt

```text
Zaimplementuj kolejny mały fragment etapu01: wykonywalne wersjonowane kontrakty
dataset/feature/label/prediction/run/tool, fixtures oraz reguły kompatybilności.
Zachowaj architektura.md i wspólne kontrakty. Uzgodnij grain, identity, lineage,
availability/as-of oraz braki i zera przed importerem i pipeline ML.
Utrzymaj działający pakiet, HTTP, DB/MLflow, migracje, Compose i required CI.
Uprawnienia nowych endpointów mają działać od pierwszej implementacji.
Nie kopiuj generatora/UI/operacyjnej DB RetailOps ani nie deklaruj modeli lub
streamingu na podstawie schema. Zapisz pozytywne i negatywne testy, evidence
i aktualny status; po push odbierz wymagane zdalne kontrole.
```
