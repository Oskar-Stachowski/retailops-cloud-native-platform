# AI 10 — dowód projektora i odczytu forecast v2

Data: 2026-10-03. Cały AI 10 pozostaje **in_progress**.
Zakres i procedury opisuje [runbook](intelligence-v2.md).

Baza branchu `ai/10-intelligence-projection`:
`ce7a93f6410b06f7c4d4e33be2212a0d65734243`.
Kontrakt ML i dokładny commit producenta są przypięte w
`services/api/app/contracts/intelligence-v2/upstream.json`.
To osobny worktree; głównego checkoutu i runtime innych sesji nie zmieniono.

| Kontrola | Wynik |
|---|---|
| Pełna regresja API poza `integration_db`/`integration_broker` | 697 passed; 5 testów wymagających dostępu do Dockera/przypiętego obrazu ponowiono: 5/5 passed. 68 testów integration wyłączono w tym przebiegu. |
| Nowa trwałość AI 10 na własnych PostgreSQL i Redpanda | 11/11 passed; rzeczywiste migracje, projekcja i API. |
| Końcowa regresja po doprecyzowaniu helperów DB | 56/56 passed: instrumentacja DB, repo metryk, consumer/runner/quarantine i kontrakt AI 10. |
| Compose config i granice lokalne | passed; bez uruchamiania wspólnego stosu. |
| Backend lint/format | passed, 229 plików sformatowanych. |
| mypy | passed, rozszerzony zakres 11 modułów. |
| Bandit high/high | passed. |
| Guard zgodności migracji i rollbacku | 25/25 testów release passed. Dokładne fingerprinty obu historycznych obrazów odpowiadają parent planu. |

Testy trwałości obejmują dokładny payload/lineage, duplicate z jednym efektem,
rollback między wynikiem a inbox, starszy wynik dostarczony później, zatrzymanie
po awarii bez luki offsetów, wadliwe raw, identity collision oraz SIGKILL po
commit przed ACK. Rzeczywisty read API sprawdza brak tokenu/obcy scope/DB outage,
102 rekordy, granice stron i zmianę zbioru między żądaniami.

JUnit jest w ignorowanym `ci-cd/reports/ai10/`. Fixtures mają jawny namespace
mechanics; transport fixture nie jest dowodem jakości ML. Pełny Required CI
dla końcowego commitu pozostaje osobną bramką PR.

Pierwszy przebieg zdalny dla `acf0dc7` zaliczył API (w tym wymagane testy DB
i brokera) oraz bramki danych/security/frontend. Dwa drille rollbacku
odrzuciły nową historię migracji zgodnie z dotychczasowym strażnikiem.
Przyrost dodaje jawny plan dokładnie jednej addytywnej migracji, zamiast
akceptować dowolny nowy head. Drille migrują własną bazę przed zapisami,
utrwalają też mechanics wynik/inbox, a następnie porównują cały schemat
i dane przy działaniu obu wersji aplikacji. Wynik kolejnego zdalnego przebiegu
musi potwierdzić tę część na dokładnym końcowym commicie.

Nie odebrano jeszcze approved-head latest, wyników AI 07/08, UI,
typed upstream REST/export/snapshot, korekt faktów, współbieżnego fencing,
shared overlay/transport auth ani całego E2E trzech modeli na profilu 102 dni.
