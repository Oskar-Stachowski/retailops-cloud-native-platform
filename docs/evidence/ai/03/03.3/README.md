# AI 03.3 — kontrakt i samowystarczalny handoff

**Odbiór lokalny: 28.09.2026.** RetailOps: branch `ai/03-01-parquet`,
implementacja `e26faa2e4733397ce7e561ebf19b65966a0d909f`, baza `ea63330`.
Repo AI: osobny worktree `/private/tmp/retailops-ai-03-03`, branch
`ai/03-03-handoff`, implementacja `654a54254e1965a3e4247aa22485684586f167e0`.
Przyjął on ukończony RAG z `origin/main` (`abf3f69`) przez merge `0785edf`;
evidence po integracji: `4376cb8`.
[Runbook](../../../../reference/source-snapshot-handoff.md) opisuje kontrakt,
CLI i granice. [Rejestr](verification.json) wiąże wyniki z wersjami i plikami.

## Dostarczony zakres

Handoff **1.0.0** przypina snapshot 1.0.0, source schema 2.6.0,
Parquet 1.0.0 i canonicalization 1.6.0. Kontrakt opisuje 25 faktowych tabel,
schemas/grain, klasy danych, mapping, jednostki, availability i watermarki,
canonical hashes, wersjonowanie i wymagane bramki. Cztery opcjonalne tabele
evaluation truth mają osobną klasę; fixture ich nie zawiera.

Fixture `data/fixtures/ai-smoke-v1` zawiera **76 plików / 2048665 B**:
contract, expected manifest i pełny snapshot (74 pliki, 25 tabel Parquet,
31171 wierszy). Wszystkie pliki są byte-identical w obu repozytoriach.
Expected manifest przypina fizyczne checksums, counts, zakresy dat/pól,
config, readiness i lineage. Seed 42, history 2026-07-02–2026-07-31,
20 produktów, 3 sklepy i 2 magazyny.

Source: `source-sha256-a12866e1099c3ae2ae7c73cac5c533a35733618d85a3728cd5f0e1c7b527fc00`.
Snapshot: `snapshot-sha256-4d856185ebbe3a8f07dc468468c54eacf69aa40b7d49bfff7e39af8ddde815a4`.

Packaging korzysta z istniejącego kwalifikowanego snapshotu. Nie uruchamia
ponownie generatora i nie przepisuje provenance: fixture zachowuje exporter
`6561481`. Wszystkie source/snapshot IDs pozostają zgodne z odbiorem 03.2.
Publikacja pakietu jest atomowa, bez nadpisania istniejącego destination.

## Wyniki kontroli

**79 testów RetailOps i 658 testów repo AI passed** — bez failures, errors
i skips. RetailOps obejmuje 8 nowych testów handoff; AI — 15. Pełne regresje
AI ponowiono po integracji z bieżącym main RAG (wcześniejsza baza: 642 testy).
Ruff/format, Bandit high/high RetailOps, Mypy AI (101 plików), checks
kontraktów, linków/Required CI, wheel, Compose config i Gitleaks przeszły.
Nowy `handoff-check` wchodzi w istniejące `make check` repo AI, a packaging
jest objęty testami i Bandit w `make data-parquet-check` RetailOps.

Upstream przelicza typed logical parity każdej tabeli. Consumer odczytuje
wyłącznie fixture, lokalny registry i checker: nie kopiuje generatora,
nie wymaga repo producenta, jego DB ani source CSV. Test detached uruchamia
checker przez `python -I` dwukrotnie, otrzymuje identyczny wynik i zachowuje
bajty wejścia. Wszystkie JSON Schema `$ref` są lokalne.

Kontrole odrzucają corruption, brakujące/dodatkowe pliki, symlink, zmienione
expected/contract, nieobsługiwane wersje, fałszywe identity, traversal
i błędną klasyfikację. W fixture nie ma users/PII, inventory, operational
AI outputs ani evaluation truth. Metadane źródła mogą opisywać wykluczone
tabele; nie są one wymaganym wejściem konsumenta.

[Benchmark](benchmark.json) dwukrotnie wykonał pełny pipeline obu smoke
w świeżych procesach: generator → kwalifikacja → eksport → verify → re-export.
Python 3.11.15, PyArrow 25.0.1, macOS arm64; pomiar na bazie `ea63330`
z kodem 03.3 w worktree. Snapshot exporter nie zmienił się w 03.3.

| Profil | Czas pełnego przebiegu | Max peak RSS | Wynik |
|---|---:|---:|---|
| ai-smoke | 16,56–17,29 s | 131,11 MiB | passed |
| ai-temporal-smoke | 28,21–35,30 s | 165,70 MiB | passed |

Limity wynoszą 300 s / 1024 MiB na profil. Łączny rozpakowany budżet
fixture i sześciu archiwów regresyjnych to **4484021 / 5242880 B**.
Jest jeden bieżący fixture; pełne/training exports pozostają poza Git.

## Następny zakres i ograniczenia

Można przejść do **03.4 — typed importer w repo AI**. Bieżący consumer checker
odbiera transport, schema i identity przypiętego fixture. Nie implementuje
typed odczytu dowolnego snapshotu, ponownego liczenia multiset canonical
hashes ani publikacji do generated. Następnie 03.5 curated i 03.6 rzeczywista
bramka cross-repo, w tym append-only/as-of, reimport i przypadki błędów.
Etapy 04 i 06 czekają na 03.6; source readiness nie kwalifikuje modeli.

Commity są lokalne. **Nie wykonano push, merge do zdalnego main ani zdalnego
Required CI AI 03.3.** Synchronizacja z istniejącym main repo AI jest lokalna.
Nie wykonano treningu, importerów DB ani nowych wywołań AWS.
