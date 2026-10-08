# AI 05 — końcowy odbiór i publikacja

**2026-10-02: etap AI 05 jest `ready`.** Odbiór obejmuje lokalny przepływ
finalnego v12 oraz publikację implementacji na chronionym `main` obu repozytoriów.
[Receipt publikacji](main-publication.json) wiąże daty odczytu, dokładne commity,
wyniki poszczególnych kontroli i nadal aktywną ochronę `main`.

| Repozytorium | Commit merge | Przyjęta zmiana | Required CI na main |
|---|---|---|---|
| retailops-cloud-native-platform | `2fd25de` | [PR #81](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/81) | [success](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/37041449945) |
| retailops-ai-intelligence | `f4ae14f` | [PR #8](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/pull/8) | [success](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/actions/runs/37043138958) |

Oba PR-y zostały scalone przy wymaganym `required-result`, aktualności względem
bazy i ochronie obejmującej administratora. Kontrole nie były wyłączane.
Joby pominięte przez istniejący wybór obszarów w RetailOps pozostają `skipped`;
receipt nie przedstawia ich jako ponownie wykonanych.

## Odbiór funkcjonalny

[Raport lokalnego przepływu](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/6dcbb223a0f3530854d6d4d7f5c7770477f7e480/docs/evidence/05-v12-real-serving.md)
z 2026-10-02 i jego przypięty JSON zachowują oryginalne czasy i pomiary.
Niniejszy zapis zamyka wymienione tam warunki publikacji; nie jest ponownym
wykonaniem prób lokalnych.

- Świeży snapshot: 56 dni obserwacji i 14 dni znanych planów, bez przyszłych faktów.
- Kwalifikacja rzeczywistego zamrożonego v12, pełna lineage, 0 refit.
- Trwały batch i API: 14/14 `current` podczas odbioru, w tym 3 zamknięte dni z `null`;
  batch 3,31 s, pierwsza strona API około 0,10 s.
- Restart PostgreSQL/MLflow/API zachowuje zadanie, hash prognoz i odczyt;
  łącznie 3 udane zadania i 42 opublikowane wiersze.
- Przetestowane reject/promote/rollback, przypięcie modelu i wejścia, lease/retry,
  atomowa publikacja, uprawnienia i scope oraz backup/restore całego stanu na fixture.

## Granice i następny etap

v12 pozostaje finalną wersją AI 04. Oryginalna jakość zachowuje **221 passed /
3 failed i `not_ready`**; trzy odstępstwa MSE są objęte wcześniejszą decyzją
właściciela. Odbiór AI 05 dotyczy osobnego namespace developerskiego i nie nadaje
zgody na produkcyjną promocję. Stare prognozy nadal przechodzą do `stale` zgodnie
z czasem; wykonanie CI nie odnawia ich origin.

Mechanika backup/restore została przyjęta na izolowanych fixture. Klon APFS
pełnej kampanii pozostaje na tym samym dysku i nie jest niezależnym backupem.
Migracja długotrwałego stosu przed jego użyciem i niezależny backup przed produkcją
pozostają osobnymi zadaniami operatora, bez zmiany lokalnego zakresu odbioru.

AI 04, 05 i 06 mają odbiór, więc można rozpocząć
[AI 08](../../../../plans/ai/etapy/08-stockout-risk.md) od weryfikacji identyfikatorów
danych, ledgeru, dojrzałości etykiet i historycznej lineage forecastu.
AI 07 jest odrębnym, nadal otwartym etapem; jego zakończenie nie jest zależnością AI 08.
Obsługa zdarzeń, brokera i projekcji wyników pozostaje zakresem AI 10.
