# Etap 11 — Zbuduj wersjonowaną wiedzę i RAG

**Repozytorium:** RetailOps AI. **Wymagany etap:** 01. Może przebiegać równolegle z danymi/ML; działający agent jest odbierany dopiero w etapie 12. Dokument nadrzędny: [kontrakt integracji i agenta](../kontrakty/integracja-agent.md).

## Cel

Odtwarzać wyszukiwanie wiedzy po zatwierdzonym korpusie Markdown i przedstawiać cytaty do konkretnego repozytorium, commitu, ścieżki i sekcji. Wyszukiwanie musi odróżniać projekt rozwiązania od dowodu jego wdrożenia. Sama obecność specyfikacji Bedrock lub Terraform nie dowodzi działającej usługi.

## Kolejność małych PR-ów

1. **Zarejestruj korpus i jego granice.** Dodaj allowlistę zatwierdzonych katalogów obu repozytoriów: dokumentacja, słowniki, opisy kontraktów, runbooki, polityki i wypełnione dataset/model/evaluation cards. Lista nie zezwala na dowolne URL/path. Wyklucz `.env`, klucze, logi, surowe transakcje, prywatne uploady, binaria modeli, niezrecenzowane pliki i simulation truth. Ustal `access_class` oraz oddzielne środowiska. Manifest wskazuje źródłowe SHA i checksums, właściciela akceptacji oraz przyczyny wyłączeń.
2. **Oznacz stan dokumentacji i fakty.** Każdy dokument ma `document_status`: `specified`, `implemented`, `verified`, `deprecated` albo `historical`; przy `verified` wskaż evidence, commit i datę weryfikacji. Pole to jest metadanymi zatwierdzanymi przez człowieka/pipeline, nie oceną LLM. Dokumenty tego planu zaczynają jako `specified`. Dla pytania „co działa?” wymagaj źródła wdrożenia/weryfikacji; specyfikację cytuj jako plan. Przy sprzecznych commitach/pomiarach zwróć konflikt lub ograniczenie, nie połącz ich w jeden fakt.
3. **Zbuduj powtarzalny parser i chunker.** Czytaj nagłówki i zachowuj ścieżkę sekcji; pomijaj nawigację/duplikaty. Nadaj `document_id`, stabilne `chunk_id`, content hash, token estimate, heading path, ordinal i wersję chunkera. Rozdziel tożsamość treści od wskazania rewizji: niezmieniony fragment zachowuje content identity, natomiast citation binding zawsze wskazuje commit bieżącego indeksu. Zmiana dokumentu usuwa z nowego indeksu nieaktualne fragmenty; nie pozostawia osieroconych chunków. Zapewnij deterministyczną kolejność.
4. **Dodaj adapter embeddings i PostgreSQL + pgvector.** Najpierw deterministyczny fake do testów offline; docelowo konfigurowalny adapter Bedrock. Manifest przypina provider, model/inference profile, region, wymiar, normalizację, odległość i wersję transformacji. Kolumna wektorowa i zapytania mają ten sam wymiar. Błąd długości embeddingu zatrzymuje budowę. Nie mieszaj przestrzeni różnych modeli w jednym indeksie i nie zmieniaj modelu pod niezmiennym ID. Zmiana modelu/wymiaru wymaga nowego indeksu; parametr modelu zweryfikuj dla wybranego regionu przy implementacji.
5. **Wprowadź immutable candidate index i atomową aktywację.** Wygeneruj `corpus_manifest.json`, `chunk_manifest.json`, `index_manifest.json` i kandydacki indeks o stałym ID. Upsert wykorzystuje checksum niezmienionych chunków; usunięte/wyłączone dokumenty nie wchodzą do nowej rewizji. Sprawdź kompletność, access metadata i golden set przed aktywacją. Zweryfikowana zmiana wskaźnika aktywnego indeksu następuje atomowo w jednej transakcji, przez kontrolowany CLI/CI. Żądanie agentowe przypina jedną wersję indeksu na cały run. Stary indeks pozostaje do rollback; nie aktualizuj połowy aktywnego indeksu w miejscu.
6. **Zaimplementuj ograniczony retrieval.** MVP: dense cosine exact search w pgvector, filtry repozytorium/typu/statusu/access class, deterministyczne top-k i tie-break po chunk ID, dywersyfikacja źródeł oraz maksymalny rozmiar kontekstu. Uprawnienia filtruj przed zwróceniem chunków, również przy cache. Kontekst oznacz jako niezaufany materiał referencyjny, a nie instrukcje. Brak właściwego źródła skutkuje `insufficient_evidence`. FTS/RRF, HNSW i reranking dodawaj tylko po pomiarze jakości/czasu; oddzielna usługa wektorowa pozostaje opcją po wykazaniu ograniczeń pgvector.
7. **Zamknij golden set, raport i administrację.** Przygotuj 30–50 wersjonowanych pytań obejmujących dokumentację, modele, operacje, brak danych, konflikt i próby injection. Dla każdego zapisz oczekiwane dokumenty/sekcje, forbidden sources, answerability, role i doc status, a także wymagane/zabronione narzędzia dla etapu 12. Przypnij progi przed ewaluacją. Zaimplementuj administracyjne index runs i read current według kontraktu; zwykły operator i agent nie mogą indeksować. Testy CI są bez AWS; rzeczywiste embeddings i Bedrock zostają potwierdzone bounded smoke w etapie 12.

## Kontrole i testy negatywne

- Takie same SHA, konfiguracja i dokumenty → identyczne content identities/manifesty logiczne; timestamp wykonania nie zmienia tożsamości. Zmiana jednego dokumentu invaliduje tylko zależne fragmenty, a usunięcie dokumentu usuwa go z candidate.
- Korpus: coverage zatwierdzonych plików, brak metadanych, duplikaty/near duplicates, orphan chunks i wykluczenia. Brakujący plik allowlisty powoduje jawny błąd lub zatwierdzone wyłączenie, nie ciche pominięcie.
- Sekrety, `.env`, raw transactions, simulation truth, arbitrary URL i ścieżka poza allowlistą są odrzucane. Adversarial corpus jest osobnym fixture testowym i nie trafia do zwykłego indeksu produkcyjnego.
- Różny wymiar embeddingu, zmiana modelu bez reindex, niekompletny indeks i nieprzechodzący golden set blokują aktywację. Przerwanie joba zostawia stary indeks aktywny. Równoczesne read i swap nie mieszają wersji; rollback odtwarza poprzedni manifest.
- Recall@k/MRR i citation correctness raportuj na prawdziwych etykietach golden set; fake embeddings dowodzą deterministyczności i działania ścieżek, nie jakości semantycznego wyszukiwania.
- Pytania „czy EKS jest wdrożony?” lub „czy RF działa w batch?” nie dostają twierdzenia o wdrożeniu na podstawie `specified`; właściwy historyczny dowód mówi, że batch w sprawdzonym commicie korzystał z moving average.
- Prompt injection w źródle nie może zmienić narzędzi, roli ani limitów; cache i retrieval nie ujawniają dokumentu niedozwolonego dla principal.

## Artefakty i Definition of Done

- Rejestr korpusu, allowlisty, manifesty i migracje pgvector; konfiguracja chunkera/embeddings oraz procedura build/validate/activate/rollback.
- Golden retrieval set i agent/tool set, osobny adversarial corpus, raport jakości z jawną listą użytych fake/real providers.
- Przykładowe cytaty i udokumentowana reguła „plan ≠ wdrożenie”; approved path/status/access filters sprawdzone testem.
- DoD: pipeline jest odtwarzalny, nie indeksuje zakazanych danych, usuwa nieaktualne fragmenty, przypina jedną wersję i przy błędzie zachowuje poprzedni aktywny indeks. Od początku zachowaj manifesty potrzebne do porównania konfiguracji RAG i driftu w etapie 13.

Proponowane interfejsy do implementacji, a nie obecnie istniejące polecenia: `make rag-index PROVIDER=fake`, `make rag-evaluate`, `make rag-activate INDEX_ID=<zatwierdzone-id>` i `make rag-rollback INDEX_ID=<poprzednie-id>`. Aktywacja jest kontrolą wdrożenia; nie należy do katalogu narzędzi agenta.

## Prompt do Codex

```text
Zrealizuj etap 11 jako małe PR-y w RetailOps AI. Użyj kontraktu
kontrakty/integracja-agent.md: allowlista Markdown, source status, manifesty,
heading-aware chunks, content identity i citation binding do SHA, pgvector,
wymiar embeddings, oddzielny candidate i atomowy swap. Najpierw dodaj fake
provider offline i meaningful tests, następnie interfejs rzeczywistego providera.
Zbuduj golden retrieval/agent sets oraz adversarial fixture. Nie uznawaj
specyfikacji za dowód wdrożenia. Nie indeksuj sekretów, raw facts ani truth.
Zapisz evidence kompletności, jakości, uprawnień, awarii i rollback. Nie dodawaj
nowej usługi wektorowej bez pomiaru wykazującego potrzebę.
```
