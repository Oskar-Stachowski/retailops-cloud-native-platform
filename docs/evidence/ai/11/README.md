# Etap AI 11 — odebrany semantyczny RAG

Aktualizacja: **2026-09-28**. Implementacja znajduje się w
`retailops-ai-intelligence`, na **`origin/main`, commit `abf3f69`** po
scaleniu [PR #4](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/pull/4).
**Etap 11 ma odbiór lokalnego semantycznego RAG.** RetailOps dostarcza część
zatwierdzonego korpusu i utrzymuje tę informację o stanie.

Źródłem wyników jest
[końcowy odbiór repo AI](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/abf3f69a6a78c444b5a8a910fef8b3b43ba047a9/docs/evidence/11-completion.md),
[rejestr pomiarów](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/abf3f69a6a78c444b5a8a910fef8b3b43ba047a9/docs/evidence/11-completion.json)
i [instrukcja](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/abf3f69a6a78c444b5a8a910fef8b3b43ba047a9/docs/knowledge-semantic.md).
Implementacja: `6790f485cfa879b0336dbf1f710f30adea06c6d0`.

## Dostępny zakres

Zatwierdzony snapshot obejmuje 29 dokumentów i 451 fragmentów z obu repo,
checksums, source status, access i cytaty do przypiętych rewizji.
Rzeczywisty provider to Amazon Titan Text Embeddings V2 w `eu-north-1`,
1024 wymiary. Build i query zachowują tę samą konfigurację przestrzeni.

Golden set ma 44 zatwierdzone pytania i 9 przypadków krytycznych, bez zmiany
pytań ani zamrożonych progów. Końcowy odbiór podaje Recall@5 **0,8529411765**
przy progu 0,80, MRR **0,6612745098** przy 0,60, kontrole krytyczne **9/9**
i powiązanie cytatów **100%**. P95 pełnego API → Bedrock → PostgreSQL
wynosi 359,12 ms przy limicie 1000 ms.

Działają trwałe runy i raporty, kwalifikacja, atomowa użytkowa aktywacja,
CAS/idempotencja, rollback oraz przypięcie niezmiennego indeksu.
Aktualny lokalny indeks ma generację 1 w `local/retrieval`. PostgreSQL
i API z rzeczywistym Bedrock odtworzyły wyniki wszystkich 44 pytań.
Odbiór obejmuje scope/auth, awarie workera, restart DB i retencję raportów.

## Dowody i granice

Końcowy odbiór właściciela repo obejmuje 643 testy regresji, 77 dodatkowych
kontroli i rzeczywisty Compose/PostgreSQL/HTTP. Ruff, Mypy, kontrakty, linki,
pakiet i Gitleaks przechodzą. Podczas AI 03.3 odczytano te dowody i scalono
opublikowane `abf3f69` do lokalnego brancha handoff; ponowiona pełna regresja
ma 658 testów, w tym 15 nowych handoff. Nie powtarzano pomiaru jakości ani
wywołań AWS. Zdalnego Required CI PR #4 nie sprawdzano ponownie w AI 03.3.

Etap 11 kończy wyszukiwanie wiedzy. Groundedness odpowiedzi, narzędzia
i pełny agent należą do [12](../../../plans/ai/etapy/12-agent-bedrock.md),
który wymaga także 10. Korpus nie odświeża się po każdej zmianie main;
kolejny snapshot potrzebuje przeglądu i ewaluacji. Odbiór nie jest wdrożeniem
AWS/EKS. Produkcyjny IAM i wdrożenie pozostają dalszym zakresem.

[Zapis zdalnego odbioru fundamentu](remote-ci.json) dotyczy wcześniejszej
publikacji `1c3b65e` i PR #3, nie bieżącego odbioru semantycznego.
Aktualną pracę opisują [backlog](../../../plans/ai/backlog.md)
i [mapa etapów/repozytoriów](../../../plans/ai/kolejnosc-i-repozytoria.md).
