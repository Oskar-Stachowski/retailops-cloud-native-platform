# Etap AI 11 — fundament offline RAG i pozostałe warunki

Aktualizacja: **2026-09-28**. Implementacja znajduje się w
`retailops-ai-intelligence`; RetailOps udostępnia część zatwierdzonego korpusu
i utrzymuje tę informację o stanie. **Etap 11 pozostaje w realizacji.**
Publikacja kodu na `main` nie oznacza włączenia RAG dla użytkowników.

Fundament offline jest na **`origin/main` repo AI, commit `1c3b65e`**,
po scaleniu [PR #3](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/pull/3).
[Required CI PR](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/actions/runs/36449464231)
oraz [Required CI push na main](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/actions/runs/36449971211)
mają `success`: checks, secrets, persistence i required-result.
Ochrona `main` pozostała aktywna.

## Dostępny zakres

Korpus ma 29 zatwierdzonych dokumentów z obu repo, przypięte rewizje Git,
checksums, statusy i klasy dostępu. Parser tworzy 451 fragmentów z cytatami;
indeks zawiera 450 rekordów testowych embeddings. Działają niemodyfikowalni
kandydaci pgvector, testowa aktywacja i rollback, ograniczony retrieval
z filtrami uprawnień/statusów oraz administracyjne runy z trwałymi raportami.

Golden set ma 44 zatwierdzone pytania i zamrożone progi. Fake Recall@5 i MRR
wynoszą 0,0441176471 wobec wymaganych 0,80 i 0,60. Kontrole krytyczne 9/9
oraz powiązania cytatów przechodzą, ale nie zastępują jakości semantycznej.
Rzeczywisty run tego korpusu prawidłowo kończy się `failed/gate_failed`,
z zachowanym raportem i bez użytkowej aktywacji.

## Otwarte warunki

1. Rozszerzyć konfigurację, kontrakty, build i query o ścieżkę rzeczywistego
   providera embeddings. Sam protokół providera już istnieje; obecna
   konfiguracja i runtime pozostają ograniczone do fake.
2. Zaimplementować i odebrać użytkową kwalifikację, aktywację i rollback.
   Obecny lifecycle działa w `test/offline_test`, a preflight fake zawsze
   blokuje użytkowe wydanie.
3. Zaliczyć progi jakości na całym zatwierdzonym golden set z rzeczywistymi
   embeddings. Nie zmieniać etykiet ani progów tylko dla uzyskania sukcesu.

Integracja real embeddings i ograniczony smoke Bedrock są przewidziane w
[12](../../../plans/ai/etapy/12-agent-bedrock.md). Smoke nie zastępuje pełnej
ewaluacji. Groundedness odpowiedzi i wykonanie narzędzi należą do odbioru
agenta; pełny 12 wymaga również ukończenia 10.

## Dowody i granice weryfikacji

- [Audyt AI 11](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/b1fb00f29e500ecdf696563ba37270158c0db3c7/docs/evidence/11-audit.md)
  dotyczy `ceec8f0`: 104 dodatkowe testy, odtworzenie całego indeksu i wyników
  44 pytań, zgodność 28 checksum oraz statyczne kontrole jakości.
- [Pełny czysty odbiór](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/b1fb00f29e500ecdf696563ba37270158c0db3c7/docs/evidence/11-golden-jobs.md)
  obejmuje 627 testów i rzeczywisty PostgreSQL/HTTP: constrainty, atomowość,
  awarie/restarty, wznowienie workera i retencję raportów. Audyt nie powtarzał
  pełnego Compose; kod od odbioru nie zmienił się.
- [PR publikujący zakres](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/pull/3)
  i [zapis zdalnego odbioru](remote-ci.json) wiążą publikację z konkretnym
  commitem i wykonaniami Required CI. Zdalny runtime to Linux AMD64.

Nie ma odbioru rzeczywistego modelu embeddings ani agenta Bedrock i nie
deklarujemy wdrożenia AWS. Dalszą pracę opisują [backlog](../../../plans/ai/backlog.md)
i [mapa etapów/repozytoriów](../../../plans/ai/kolejnosc-i-repozytoria.md).
