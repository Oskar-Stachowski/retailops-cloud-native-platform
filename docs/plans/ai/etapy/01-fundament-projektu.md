# 01 — Architektura, repozytoria i szkielet AI

**Repo:** oba; nowe komponenty w AI. **Zależność:** 00. **Rezultat:** działający fundament lokalny bez deklaracji gotowych modeli.

**Stan bieżący:** osobne repo `retailops-ai-intelligence` zawiera pakiet,
settings, CLI, HTTP oraz PostgreSQL/pgvector AI i oddzielną bazę/rolę MLflow.
Działają migracje, Compose i wersjonowane kontrakty danych/run/tool z fixtures
oraz semantyczną walidacją offline. [Dowody](../../../evidence/ai/01/README.md)
obejmują 208 testów na czystym checkoutcie i wheel poza źródłami; osobny wcześniejszy
pomiar persistence potwierdza rzeczywisty crash/restart i DB outage/recovery.
Main na GitHub ma required-result, CI bazowego 7d67530 ma success.
Nowe commity są lokalne i czekają na zdalny CI po push. Etap pozostaje in_progress.

Przeczytaj [architekturę](../architektura.md) i wspólne kontrakty w `../kontrakty/`.
Grain/identity/availability pierwszej prognozy są wykonywalne w v1 repo AI;
importer, model training, auth i pełne zdarzenia wymagają własnych implementacji.

## Pozostała praca

7. **Tożsamość, uprawnienia i zdalny CI.** Zweryfikuj principal i egzekwuj
   role/scopes nowych endpointów aplikacyjnych od ich pierwszej implementacji.
   Odrzucaj próby rozszerzenia scope, tokeny poza Git/logami. Token metryk i
   caller-supplied user_id nie są tożsamością użytkownika. Nie używaj demo-admina
   RetailOps jako domyślnej tożsamości agenta. Rozwijaj bramki nowych komponentów;
   po push odbierz ich Required CI, w tym persistence. Zachowaj ochronę main.
8. **Status i polecenia.** Rozwijaj istniejące make/CLI/Compose razem z aplikacją,
   bez pustych targetów training/deploy. Aktualizuj rejestr etapu i evidence.

## Ustawienia i granice

Konfiguracja docelowa obejmuje APP_ENV, DATABASE_URL, MLFLOW_TRACKING_URI, RETAILOPS_API_URL, KAFKA_BOOTSTRAP_SERVERS, region/model allowlist Bedrock, ścieżki artefaktów i OTEL endpoint. Wartości środowiskowe nie trafiają na sztywno do domeny. `.env.example` zawiera wyłącznie bezpieczne placeholdery.

W fazie K1 wykonanie jest lokalne. Brak źródła RetailOps powoduje kontrolowany błąd importu; brak opcjonalnego LLM — czytelny status degraded. Nie ukrywaj awarii użyciem przypadkowego modelu ani danych syntetycznych, których użytkownik API nie zamówił.

## Kontrole następnego zakresu

- Verified principal i brak/niepoprawne poświadczenia → 401; brak prawa → 403.
- Scope produktu/selling location/kanału jest egzekwowany, role/body/query nie
  rozszerzają uprawnień. Nowe endpointy administracyjne wymagają właściwej roli.
- Tokeny i prywatne dane nie występują w błędach/logach. Kontraktowe odmowy
  nie zmieniają bezpiecznej diagnostyki health/readiness/version.
- Pozytywne i negatywne testy auth działają bez konta AWS, w lokalnym required CI.
- Dotychczasowy bootstrap, kontrakty, package, HTTP/DB sondy i migracje przechodzą;
  po push nowy zdalny Required CI ma success i main zachowuje required-result.

Zapisz ADR-y, listę uruchomionych poleceń i ograniczenia. Etap odblokowuje dane02, RAG11 oraz projektowanie16A po określeniu infrastrukturalnego input contract.

## Prompt

```text
Zaimplementuj kolejny mały zakres etapu01: tożsamość i uprawnienia pierwszych
endpointów aplikacyjnych. Uzgodnij verified principal, role/scopes i źródło
poświadczeń. Egzekwuj dostęp od pierwszej implementacji; caller-supplied ID,
body/query i token metryk nie mogą zastąpić zweryfikowanej tożsamości.
Testuj 401/403, scope produktu/selling location/kanału, próby podmiany roli
oraz brak sekretów w odpowiedziach/logach, bez AWS.
Utrzymaj pakiet, kontrakty v1, HTTP, DB/MLflow, migracje, Compose i required CI.
Nie kopiuj demo-admin RetailOps ani nie deklaruj production IAM, agenta lub
serving na podstawie warstwy auth. Zapisz evidence i aktualny status;
po push odbierz wymagane zdalne kontrole nowych commitów.
```
