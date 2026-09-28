# Etap AI 11 — odebrany semantyczny RAG

**2026-09-28 · completed.** Implementacja należy do
`retailops-ai-intelligence`; cloud-native dostarcza część zatwierdzonego korpusu
oraz utrzymuje ten status. [PR #4](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/pull/4)
opublikował pełne domknięcie na `origin/main` (`abf3f69`).
Required CI [PR](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/actions/runs/36460532011) i [push na main](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/actions/runs/36461392661)
ma `success`, łącznie z persistence. Ochrona main pozostała włączona.
Szczegóły: [zapis zdalny](remote-ci.json).

## Odbiór

Zatwierdzony korpus ma 29 dokumentów, 451 fragmentów i 451 embeddings z kontekstem
nagłówków. Provider to **Amazon Titan Text Embeddings V2**, `eu-north-1`,
1024 wymiary. Przypięte są model, region, wymiar, normalizacja i transformacja;
zmiana konfiguracji tworzy inną przestrzeń oraz nowy indeks.

Na tych samych 44 pytaniach, bez zmiany etykiet ani progów:

| Metryka | Wynik | Próg |
|---|---:|---:|
| Recall@5 | 0,852941 | ≥ 0,80 |
| MRR | 0,661275 | ≥ 0,60 |
| Krytyczne / cytaty | 100% / 100% | 100% / 100% |
| P95 API → Bedrock → PostgreSQL | 359,12 ms | ≤ 1000 ms |

Właściwy run `run-ad4e22256eee6be6fe415bb848e46589` ma `succeeded`.
Kwalifikowany indeks `index-sha256-d193c015d0815215725156145cef5ed21553452e1c235d0c8e4cabece96d9f46`
został aktywowany w `local/retrieval`, generacja 1. PostgreSQL odtworzył wszystkie
44 wyniki; odbiór przez API z rzeczywistym Bedrock zachował dokładne chunk IDs.
38 żądań dotarło do modelu; niedozwolony scope odrzucono przed AWS.

Działają trwałe profile/runy, retencja raportów przy niezaliczonym progu,
kwalifikacja jakości, atomowa aktywacja, CAS, retry, rollback i stare piny.
Konfiguracja query pochodzi z zaakceptowanego release. Fake nie uprawnia
użytkowej aktywacji, a udany run wymaga osobnej kwalifikacji i aktywacji.

## Dowody i granice

- [Końcowy odbiór AI](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/72abb8b222f00fa4660288eb37d8d68443374cd6/docs/evidence/11-completion.md)
  oraz [pomiary/checksums](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/72abb8b222f00fa4660288eb37d8d68443374cd6/docs/evidence/11-completion.json).
- Implementacja `6790f485cfa879b0336dbf1f710f30adea06c6d0`; 643 testy regresji,
  77 testów po dopracowaniu current/report, Ruff, strict Mypy, schemas,
  docs, wheel/sdist i Gitleaks.
- Pełny Compose: `0008_rag_semantic`, rzeczywisty pgvector/HTTP, negatywne SQL gates,
  aktywacja/rollback, awarie, SIGKILL/down-up i retencja danych. CI bez AWS;
  syntetyczne fixture nie są dowodem jakości modelu.
- [Instrukcja użytkowa](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/72abb8b222f00fa4660288eb37d8d68443374cd6/docs/knowledge-semantic.md)
  opisuje poświadczenia, jawny opt-in AWS, limity, cache, reindex i rollback.

**Nie ma otwartych blokad AI 11.** Korpus jest konkretnym snapshotem;
zmiany `main` nie aktualizują go automatycznie. Groundedness odpowiedzi,
narzędzia i integracja agenta należą do AI 12, którego pełne zamknięcie wymaga
również AI 10. Produkcyjne role, wspólne budżety replik oraz wdrożenie AWS/EKS
należą do późniejszych etapów. W tym odbiorze wykonano ograniczone wywołania
Bedrock, bez wdrażania infrastruktury chmurowej.

[Backlog](../../../plans/ai/backlog.md) i [mapa etapów](../../../plans/ai/kolejnosc-i-repozytoria.md)
podają dalszą kolejność. Aktualny główny strumień to AI 03; interfejsy/test doubles
AI 12 można przygotowywać równolegle.
