# AI 08 — końcowy odbiór

**2026-10-05: AI 08 jest READY.** [Receipt obu repozytoriów](main-publication.json)
przechowuje dokładne przyjęte commity, wyniki jobów oraz granice odbioru.
[Pełny raport repo AI](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/2565a216fa7807a756387dcbaa408d6ccc07840d/docs/evidence/08-27-final-serving-acceptance.md)
i [scalony PR #14](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/pull/14)
zachowują właściwe dowody implementacji.

| Zakres | Zakończony odbiór |
|---|---|
| Źródło RetailOps | main `684f18f`, [Required CI success](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/runs/37262096351); przygotowane matching i późniejsze stress na seedach 42/137/2026. |
| Model i runtime AI | main `2565a21`, [Required CI success](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/actions/runs/37288700026), 2543 testy; [PR CI success](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/actions/runs/37282434148). |
| Niezależna jakość | 9296 punktów, 90 kontroli passed, 3 zaakceptowane ostrzeżenia małych kategorii, 0 blokad; [pełne wyniki](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/2565a216fa7807a756387dcbaa408d6ccc07840d/docs/evidence/08-25-final-campaign-results.md). |
| Karta i polityka | LR with_upstream + conditional sigmoid C10; progi 25/50/90%, capacity top50%; [kwalifikacja](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/2565a216fa7807a756387dcbaa408d6ccc07840d/docs/evidence/08-26-qualified-model.md). |
| Serving i awarie | 206 focused tests, 12 review gates; rzeczywisty SQL/MLflow, register/promote/rollback/reject, cold worker, 40 wyników batch, 15 attention, HTTP auth/scope/idempotency i backup/restore. |

DoD [etapu 08](../../../../plans/ai/etapy/08-stockout-risk.md) obejmuje dojrzałe
incident-stockout7d, fizyczny zapas, PIT, rolling-origin upstream, temporal splits,
LR/HGB, kalibrację i development policy, model card oraz wspólny lifecycle/batch/API.
Wszystkie te zakresy są przyjęte. Pozostałe wymagane prace AI 08: **0**.

Próg ostrzeżeń małych kategorii został zatwierdzony przed final oceną; pierwotne
strict calibration failures pozostają widoczne. Modele i policy nie zostały
ponownie dopasowane. Dane syntetyczne nie dowodzą generalizacji u rzeczywistego
retailera. Koszty FP/FN są ilustracyjne, okna nie są niezależnymi epizodami.
Odbiór był izolowany i nie oznacza wdrożenia produkcyjnego.

AI 04/v12 z trzema przyjętymi odstępstwami MSE oraz AI 05 mają wcześniejszy
[odbiór](../../05/final/README.md). Ich statusy w indeksie zostały zsynchronizowane
z tym istniejącym dowodem. AI 07 zachowuje osobny odbiór; zależności 09/10 są w
[indeksie etapów](../../../../plans/ai/etapy.json). Nie otwieraj ponownie AI 08
na podstawie wcześniejszych historycznych wpisów not ready.

Receipt zapisuje odbiór przyjętych rewizji kodu. Późniejsza publikacja dokumentacji
przechodzi przez osobne chronione PR-y i istniejące Required CI.
