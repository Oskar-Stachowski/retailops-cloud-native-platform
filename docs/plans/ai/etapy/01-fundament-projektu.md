# 01 — Architektura, repozytoria i szkielet AI

**Repo:** oba; nowe komponenty w AI. **Zależność:** 00. **Rezultat:** działający fundament lokalny bez deklaracji gotowych modeli.

Przeczytaj [architekturę](../architektura.md) i wspólne kontrakty w `../kontrakty/`. Model danych/ziarno/availability uzgodnij przed implementacją pipeline’ów; pełne zdarzenia zostaną uruchomione w 10.

## Praca w małych PR-ach

1. **Repo i zasady.** Utwórz lub uporządkuj osobne `retailops-ai-intelligence`; README mówi `planned/in_progress`, nie „production ready”. Dodaj `.gitignore`, wzory środowiska, zasady PR/contributing/security i decyzję o licencji. W ADR zapisz granice i decyzje z architektury. Nie przenoś generatora, frontendu ani operacyjnych modeli DB RetailOps.
2. **Pakiet Python.** Wybierz jedną wspieraną wersję Python, kompatybilną ze scikit-learn i TensorFlow na środowisku docelowym, oraz jeden manager/lockfile. Utwórz `src/retailops_ai`, importowalny package, typed settings i CLI. Rozdziel API/domenę/adapters/pipelines. Późniejsze komendy korzystają z tego samego kodu co jobs.
3. **Serwis bazowy.** Dodaj `GET /health`, `/ready`, `/version`, `/metrics`; correlation ID, logi JSON, trace propagation i wspólny error contract. Health oznacza działający proces, readiness wymagane zależności konkretnej roli. Brak Bedrock nie wyłącza odczytu poprawnych predykcji ML.
4. **Persistence.** Dodaj PostgreSQL dla AI, migracje Alembic, oddzielną bazę i użytkownika MLflow; pgvector tylko w bazie AI. Zaplanuj rozdzielenie metadata od dużych artefaktów. Migracje są jawne, nie uruchamiane konkurencyjnie przy starcie każdego poda.
5. **Compose.** Postaw API/Postgres/MLflow z lokalnymi wolumenami i health checks. Provider fakes pozwalają wykonać testy bez AWS. Nowy Compose nie definiuje drugiego brokera RetailOps. Pełne external networking oraz event worker wymagane w10; opcjonalny worker nie jest konieczny do pierwszego zdrowego serwisu.
6. **Wspólne kontrakty.** Nadaj wersje dataset/feature/label/prediction/run/tool schemas; wzory w tym pakiecie przełóż na wykonywalne modele i fixtures w repo. Zapisz semantykę braków, zer, czasu i source ownership. Event schema inventory jeszcze nie oznacza działającego streamingu.
7. **CI i zabezpieczenia od początku.** Uruchom lint/type/package/test/docs/contracts i secret scan. Ustal required-result oraz detekcję ścieżek; własne endpointy administracyjne od początku mają granicę dostępu. Sekrety poza Git i logami. Używaj ról o ograniczonym zakresie, nie demo admina RetailOps jako domyślnej tożsamości agenta.
8. **Status i polecenia.** Udostępnij minimalne docelowe `make bootstrap`, `make test`, `make compose-up`, `make compose-down`. Nie dopisuj pustych targetów udających działający trening/deploy. Aktualizuj rejestr etapu i evidence.

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
Zaimplementuj wskazany mały fragment etapu01 RetailOps instrukcja.
Zachowaj architektura.md i wspólne kontrakty. Utwórz działający szkielet AI:
package/settings/CLI, health/ready/version/metrics, logi i correlation, jawne
migracje, oddzielne persistence AI/MLflow oraz Compose i podstawowe required CI.
Użyj fakes dla providerów. Wersjonuj kontrakty i ADR-y, nie kopiuj generatora/UI/DB
RetailOps. Nie twierdź, że modele lub nowe zdarzenia już działają. Dokończ fragment
z pozytywnymi/negatywnymi testami i evidence, aktualizując stan etapu.
```
