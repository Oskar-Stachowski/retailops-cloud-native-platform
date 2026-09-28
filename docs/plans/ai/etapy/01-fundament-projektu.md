# 01 — Architektura, repozytoria i szkielet AI

**Repo:** oba; nowe komponenty w AI. **Zależność:** 00. **Rezultat:** działający fundament lokalny bez deklaracji gotowych modeli.

**Stan bieżący:** osobne repo `retailops-ai-intelligence` zawiera pakiet,
settings, CLI, HTTP, PostgreSQL/pgvector AI i oddzielny MLflow, migracje/Compose,
kontrakty danych/run/tool oraz lokalne poświadczenia i uprawnienia API.
[Dowody](../../../evidence/ai/01/README.md) obejmują 267 testów na czystym checkoutcie
oraz rzeczywisty HTTP z wheel poza źródłami. Principal pochodzi z prywatnej mapy;
endpointy identity, preflight scope i admin metadata mają kontrolę 401/403.
Lokalny zakres ma odbiór. Etap pozostaje in_progress do zdalnego CI nowych commitów.
Osobny wcześniejszy pomiar persistence zachowuje własną datę i zakres.

Przeczytaj [architekturę](../architektura.md) i wspólne kontrakty w `../kontrakty/`.
Grain/identity/PIT są wykonywalne w v1. Lokalny auth nie jest produkcyjnym IdP;
zmiana polityki wymaga restartu, a forecast-check nie odczytuje modelu/danych.
Importer, ML pipelines, właściwe serving APIs i pełne zdarzenia mają własne etapy.

## Pozostała praca

7. **Zdalny CI i odbiór.** Po push nowych commitów odbierz Required CI dokładnego
   SHA: checks, secrets, persistence i required-result. Utrzymaj ochronę main.
   Popraw ewentualne błędy i ponów odbiór nowej rewizji, bez pomijania bramek.
8. **Status i dowody.** Zapisz URL/revision/wynik workflow i stan ochrony main.
   Po rzeczywistym odbiorze zamknij rejestr 01 oraz wskaż DATA-01 etapu 02 jako
   następną implementację. Nie nazywaj lokalnego testu zdalnym CI.

## Ustawienia i granice

Konfiguracja docelowa obejmuje APP_ENV, DATABASE_URL, MLFLOW_TRACKING_URI, RETAILOPS_API_URL, KAFKA_BOOTSTRAP_SERVERS, region/model allowlist Bedrock, ścieżki artefaktów i OTEL endpoint. Wartości środowiskowe nie trafiają na sztywno do domeny. `.env.example` zawiera wyłącznie bezpieczne placeholdery.

W fazie K1 wykonanie jest lokalne. Brak źródła RetailOps powoduje kontrolowany błąd importu; brak opcjonalnego LLM — czytelny status degraded. Nie ukrywaj awarii użyciem przypadkowego modelu ani danych syntetycznych, których użytkownik API nie zamówił.

## Kontrole odbioru zdalnego

- Wszystkie jobs Required CI nowych commitów mają success dla dokładnego SHA.
- Job persistence wykonuje rzeczywisty Compose smoke, a required-result wymaga
  jego wyniku razem z checks/secrets. Skipped/cancelled nie są success.
- Main zachowuje required-result i zasady PR; nie osłabiaj bramek dla merge.
- Evidence odróżnia lokalny macOS/ARM64, zdalny Linux/AMD64 oraz przyszłe AWS.
- Lokalny auth i nowe endpointy nie deklarują OIDC, production serving lub agenta.

Zapisz ADR-y, listę uruchomionych poleceń i ograniczenia. Etap odblokowuje dane02, RAG11 oraz projektowanie16A po określeniu infrastrukturalnego input contract.

## Prompt

```text
Odbierz pozostałą zdalną bramkę etapu01 po push nowych commitów repo AI.
Sprawdź Required CI dokładnego SHA: checks, secrets, persistence i required-result
muszą mieć success. Zachowaj ochronę main i PR-before-merge; nie pomijaj smoke
ani nowych ścieżek/contracts. Popraw znalezione błędy i odbierz nowy SHA.
Zapisz URL/revision/środowisko/wynik workflow oraz stan ochrony main w evidence.
Po rzeczywistym odbiorze zamknij 01 w rejestrze i aktywnym planie. Następną
implementacją będzie DATA-01 etapu02, bez zmiany legacy demo lub bramek późniejszych AI.
```
