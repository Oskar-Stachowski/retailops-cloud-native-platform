# Otwarte ustalenia audytowe

Pomiary bazowe: **27.09.2026**, baza `cbf28b2a66e7e5f205cf73d9bfe620c491e22d93`.
Aktualizacja otwartego zakresu: **30.09.2026**.
Poniżej są wyłącznie otwarte problemy potwierdzone w źródłach lub reprodukcji.
[Audyt AI 00](../evidence/ai/00/README.md) rozdziela pomiary, 138 testów,
przegląd statyczny i odczyt CI; nie potwierdza gotowości wszystkich dalszych
etapów ani wdrożenia produkcyjnego.
Kolejność pracy i pierwsze małe PR-y: [backlog AI](../plans/ai/backlog.md).
[Audyt AI 02](../evidence/ai/02/audit/README.md) potwierdza
gotowość źródła 2.6. [Odbiór AI 03](../evidence/ai/03/03.6/README.md)
otwiera forecasting 04 oraz ledger 06; poniższe problemy mają własne dalsze bramki.

**P1** oznacza ryzyko utraty danych, naruszenia granicy dostępu lub niewiarygodnej
oceny modelu. **P2** oznacza problem odtwarzalności, izolacji lub diagnostyki.
Priorytet dotyczy wskazanego zastosowania, a nie deklaracji gotowości produkcyjnej.

## Źródło danych AI

Pomiary DATA-01–06: [source-measurements.json](../evidence/ai/00/source-measurements.json),
profil `small`, 90 dni, 100 produktów, seed 42. Nie są pomiarami danych rzeczywistych.

## Runtime i bezpieczeństwo

### OPS-06 · P2 · Zależności builda i workflow są wskazywane ruchomymi tagami

**Dowód:** [Dockerfile API](../../services/api/Dockerfile) i
[Dockerfile frontendu](../../frontend/Dockerfile) używają tagów bazowych bez
digestów. Zewnętrzne actions, także w
[workflow wydania](../../.github/workflows/release.yml), są wskazywane tagami
takimi jak `actions/checkout@v6`, nie pełnym SHA. Identyczny commit repozytorium
nie identyfikuje zatem jednoznacznie wszystkich wejść przyszłego builda.

**Kryterium zamknięcia:** pełne SHA dla zewnętrznych actions oraz digesty bazowych
obrazów, aktualizowane kontrolowanym PR z walidacją. Dowód wydania zapisuje
rozwiązane tożsamości wejść i wynikowych artefaktów.
