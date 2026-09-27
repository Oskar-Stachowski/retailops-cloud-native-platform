# Operacje, promocja, awarie, rollback i cleanup

**Status:** docelowy runbook. Podane niżej cele `make` i CLI są interfejsem do zaimplementowania, a nie potwierdzeniem istnienia komend w obecnym repo. Podczas wdrażania zastąp je rzeczywistymi, przetestowanymi poleceniami; wpisz commit, środowisko, datę ostatniego ćwiczenia i link do evidence. Nie oznaczaj runbooka jako zweryfikowanego bez wykonania go z czystego środowiska.

## 1. Reguły wspólne

- Każda operacja wskazuje środowisko, oba commity, dataset/config/release refs, tożsamość operatora oraz spodziewany efekt. Polecenie dotyczące lokalnej DB ma odmówić pracy przy URL niezgodnym z local allowlistą.
- Przed zmianą utrwal stan i recovery reference. Kontrole dostępności nie zastępują kontroli wersji, integralności i świeżości wyników.
- Rutynowy development używa syntetycznych fixture'ów oraz fake provider; live Bedrock ma jawny limit czasu, tokenów, requestów i kosztów.
- Nie usuwaj danych RetailOps, współdzielonych sieci, cudzych state ani artefaktów wymaganych do rollbacku. Do resetu wolumenów AI i cloud destroy służą osobne, celowane procedury z planem zakresu.
- Sekrety, raw prompts, pełne source records i ukryte rozumowanie nie trafiają do evidence. Zachowaj zwięzły wynik i odnośnik do kontrolowanego źródła.

Wymagane metadane ćwiczenia: `started_at`, `finished_at`, `environment`, `retailops_commit`, `ai_commit`, `release_id`, `command`, `expected`, `actual`, `result`, `recovery`, `remaining_limitations`.

## 2. Lokalny start i wyłączenie

### Warunki

Git, Docker/Compose, wybrane narzędzie Python/lockfile, make, dostęp do obu repo i deklarowane RAM/CPU/dysk. Dla kind także kubectl, Helm, kind i CNI z egzekwowaniem NetworkPolicy. Wersje zapisuje etap 14. Nie zakładaj portów — w `.env.example`/README utrwal finalny, bezkolizyjny zestaw, np. AI 8100, MLflow 5000, Prometheus 9091, Grafana 3002, o ile jest zgodny z aktualnym RetailOps.

### Procedura docelowa

1. Checkout przypiętych commitów i instalacja z lockfile. Przygotuj lokalne `.env` z oczywistych przykładów, bez commitowania wartości. Wybierz `LLM_PROVIDER=fake` i `EMBEDDING_PROVIDER=fake`.
2. Uruchom RetailOps według jego aktualnego runbooka; potwierdź health i seed/demo. Zastosuj zatwierdzony Compose overlay łączący `api`/`redpanda` do wspólnej external network. Sprawdź alias API oraz Kafka advertised listeners.
3. Uruchom zależności AI i jawne migracje, potem API/worker. Domyślnie AI nie ma dostępu do DB RetailOps.
4. Uruchom smoke API/MLflow/AI DB oraz connectivity REST/broker. Po restarcie sprawdź trwałość metadanych. Następnie import snapshotu i data gates; start modeli/agenta tylko z zatwierdzonych refs.

Proponowany interfejs w **repo AI**, do implementacji i sprawdzenia:

```bash
make bootstrap
make compose-up
make migrate
make api-smoke
make mlflow-smoke
make database-smoke
make broker-connectivity-smoke
make data-sync PROFILE=ai-smoke
make data-validate PROFILE=ai-smoke
```

`ai-smoke` wymaga wariantu odpowiedniego do zadania: krótki fixture transport/schema nie dowodzi temporal training readiness. Temporal smoke ma osobny warmup, scoring i label tail zgodnie z [profilami](../kontrakty/profile-i-bramki.md).

Oczekiwany dowód: status usług, `/version`, manifest, checksums, odpowiedź API, identyczne dataset ID po powtórnym imporcie oraz brak duplikatów. Przy błędzie ustal najpierw konfigurację/identity/network, potem storage i application log; nie kasuj DB jako pierwszego kroku.

### Zatrzymanie/reset

Docelowe `make compose-down` zatrzymuje tylko projekt AI; osobno zatrzymujemy RetailOps w jego repo. Nie wykonuje `down -v` dla współdzielonych projektów. `make local-clean-generated` obejmuje wyłącznie zadeklarowane artefakty robocze AI. `make local-reset-all-ai` musi wypisać konkretny zakres wolumenów, sprawdzić środowisko i respektować wymagany mechanizm potwierdzenia repo. Zwykły restart nie usuwa stanu. Sieć współdzielona ma właściciela i może być usunięta dopiero, gdy żaden projekt jej nie używa.

## 3. Codzienny cykl ML/RAG i kontrolowany Bedrock

Proponowane komendy po ich implementacji:

```bash
make train-smoke
make evaluate-smoke
make batch-inference PROFILE=ai-dev
make drift-check PROFILE=ai-dev
make rag-index PROVIDER=fake
make rag-evaluate
make agent-evaluate PROVIDER=fake
```

Przed pełnym treningiem sprawdź use-case-specific gates, split manifest, dojrzałość labeli i brak simulation truth w features. Promocja nie jest efektem ubocznym treningu. Fake embeddings nie są dowodem jakości retrieval modelu Bedrock; indeksy providerów i ich wymiary mają różne wersje.

Przed bounded live smoke: potwierdź aktualne konto/region/krótkotrwałą tożsamość, dozwolony model/profile, corpus i limity; uruchom najmniejszy golden case chat oraz embeddings, zapisz usage, elapsed time i wynik. Proponowane `make bedrock-smoke` oraz `make agent-demo PROVIDER=bedrock` muszą odmówić pracy bez jawnego live mode. Awaria dostawcy kończy się kontrolowanym statusem, nie automatycznym podnoszeniem limitu/retry.

## 4. Promocja modelu i release'u

### Preconditions

Zatwierdzony dataset/features/splits, final evaluation i model card, baseline comparison/segmenty, poprawne metryki zer oraz drift, podpis/skróty artefaktów, load/inference w obrazie docelowym, test kompatybilności, owner z prawem promocji, poprzedni kompletny release i backup/recovery DB. Jeśli wymagana jest kalibracja/threshold, ich wersja należy do artefaktu release'u. Nowy model nie może wymaganiem feature schema unieważniać działającego runtime bez planu migracji.

### Procedura

1. Odczytaj wersję kandydata, lineage i ewaluację. Zapisz decyzję `approve` lub `reject` z uzasadnieniem; odrzucenie nie usuwa wyników eksperymentu.
2. Zablokuj współbieżne promocje tego modelu. Zapisz poprzednie aliasy i release refs. Zweryfikuj artefakt według niezmiennej wersji/checksum.
3. Przygotuj nowy release i GitOps PR. Alias `champion`/`rollback` jest metadanymi lifecycle; API przy starcie używa zatwierdzonej wersji liczbowej i checksum z release'u. Przestawienie aliasu nie jest deploymentem.
4. Przy zmianie aliasów prowadź audyt kroków i recovery po częściowym powodzeniu — operacje registry/Git/cluster nie są jedną transakcją. Po błędzie najpierw odczytaj faktyczny stan przed retry.
5. Wdróż zgodne migracje expand, następnie immutable release; wykonaj startup/readiness, `/version`, inference/schema/freshness oraz post-sync smoke. Dopiero potem oznacz release jako udany. Zachowaj poprzedni artefakt.

Proponowany interfejs:

```text
make model-review MODEL=<name> VERSION=<immutable-version>
make model-promote MODEL=<name> VERSION=<version> EVALUATION_ID=<id>
make inference-smoke MODEL=<name>
```

Każde polecenie promujące musi sprawdzić gate/audit; sam podany parametr nie jest uprawnieniem. Testowana implementacja opisuje kolejność aliasów i GitOps oraz postconditions; nie nazywaj jej atomową, jeśli nie ma takiej gwarancji.

## 5. Reakcja na incydent

1. Zapisz czas, środowisko, wpływ, trace/run/correlation i komplet release refs. Zachowaj evidence przed zmianą.
2. Ustal granicę problemu: source, feature, model, broker/projection, RAG/agent czy platforma. Sprawdź świeżość i liczebność, nie tylko HTTP 200.
3. Ogranicz skutek: zawieś konkretny job/publication lub assistant endpoint, oznacz dane stale/unavailable, wstrzymaj promocję. Nie przeuczaj ani nie promuj automatycznie.
4. Wybierz naprawę, replay, rollback albo dalszą obserwację na podstawie dowodów. Wyznacz ownera i warunek odzyskania.
5. Zweryfikuj wynik domenowy, wersje, zdrowie, kolejkę/outbox, idempotencję i integralność. Zamknij alarm dopiero po recovery; zapisz przyczynę, poprawkę testu/alertu i pozostałe ograniczenia.

| Sygnał | Pierwsza kontrola | Dopuszczalna reakcja |
|---|---|---|
| Source/feature drift | Manifest, schema, freshness, kod i dostępność PIT | Zatrzymaj dotknięte inference; popraw dane/kod, nowe feature ID |
| Performance drift | Dojrzałe labels, pełne okno, baseline i segmenty | Kandydat do retreningu lub rollback po analizie; brak automatycznej promocji |
| Forecast bias/stockout | Observed sales censoring, mapping stock, plany vs outcomes | Popraw policy/evaluation, nie używaj simulation truth jako wejścia |
| DLQ/lag/outbox | Broker, schema version, DB, granica ACK, duplicates | Napraw przyczynę, replay z kontrolą zakresu i idempotencji |
| Model load | Runtime version/checksum, registry/artifact permissions | Wstrzymaj release; odtwórz zatwierdzony artefakt |
| RAG regression | Corpus commit, chunking, embedding model/dimension, index | Wstrzymaj indeksację, przełącz zatwierdzony poprzedni index |
| Agent failure | Golden case, tool auth, config, provider usage/timeouts | Wyłącz/ogranicz asystenta; klasyczne reads pozostają dostępne |
| Kubernetes rollout | Git desired state, pod events, migration Job, DB | Oceń częściowy stan; odtwórz spójny release przez Git |

SEV-1: ujawnienie/corruption danych, sekret, nieuprawniony write lub artefakt; natychmiastowe containment i odwołanie dotkniętego dostępu. SEV-2: błędny model albo niedostępność/niepoprawność wszystkich predykcji. SEV-3: opóźniony job, kontrolowana degradacja dostawcy, drift warning. SEV-4: niekrytyczna wada dashboardu/docs. Komunikację prowadzi uprawniony właściciel według kanału projektu; ten dokument sam nie wysyła wiadomości.

## 6. Zdarzenia i replay

Przed resetem offsetów zanotuj topic/partition/range, snapshot watermark, kanoniczną wersję kontraktu i przyczynę awarii. Ustal adapter legacy/v2, żeby nie mieszać granulatów i topiców. Powtórzony event ID nie tworzy ponownie faktu, a starsza predykcja nie zastępuje nowszej.

Proponowane `make consumer-status` i `make dlq-summary` pokazują stan bez wypisywania wrażliwych payloadów. Replay musi być ograniczony zakresem i mieć dry-run/preview liczebności. DB error przed commit nie może ACK; crash po commit przed ACK ma bezpieczny retry. Gdy invalid JSON nie daje się trwale zapisać do DLQ, offset nie jest zatwierdzany. Nie zatwierdzaj późniejszego offsetu ponad nieobsłużoną luką partycji.

Po replay sprawdź konkretny read model RetailOps i lineage, nie sam wzrost licznika „consumed”. Zapisz expected/actual rows i brak duplikatów. Operacja nie może przy okazji dopisywać drugi raz historii zawartej już w snapshot.

## 7. Spójny rollback aplikacji, modelu i agenta

1. Wybierz ostatni **kompletny i zgodny** release, nie tylko poprzedni image lub alias. Sprawdź dostępność wszystkich artefaktów, index/embedding schema, DB compatibility i backup.
2. Wstrzymaj nową promocję i publikację dotkniętych wyników. Zapisz stan faktyczny, ponieważ częściowy Argo sync mógł już zmienić środowisko.
3. Przygotuj GitOps revert/PR z pełnym zestawem image/model/config/index/feature/schema refs. Jeśli stary runtime nie jest zgodny ze zmienioną DB, zastosuj wcześniej zatwierdzoną procedurę forward-fix lub restore; cofnięcie obrazu nie cofa destrukcyjnej migracji.
4. Zsynchronizuj desired state, obserwuj startup/readiness i przeprowadź smoke. W auto-sync popraw także Git; ręczny rollback bez Git zostanie ponownie nadpisany.
5. Potwierdź `/version`, prognozę/anomalię/ryzyko, agenta z właściwym indeksem, worker i brak naruszonej deduplikacji. Odtwórz batch outputs tam, gdzie konieczne, z nowym run ID i jawnym supersession, bez wymazywania historii.
6. Dopiero po potwierdzeniu oznacz recovery i uzgodnij lifecycle aliases. Przy registry outage pozostaw już załadowany zatwierdzony model, jeżeli działa, i wstrzymaj promocję. Nie pobieraj zastępczego modelu z niezaufanego źródła.

Evidence: before/after refs, GitOps commit, audit, powód, health i domain smoke, wpływ na batch/outputs, ewentualny restore i końcowa integralność.

## 8. AWS apply/showcase/cleanup

Szczegóły [etapu 16](../etapy/16-aws.md) są obowiązujące. Przed startem potwierdź konkretne konto, region, krótkotrwałą tożsamość, plan i ownera każdego zasobu. Użyj chronionego workflow dla apply. Cena w kosztorysie i alert Budget nie są blokadą wydatków; ogranicz runtime i zakończ pokaz zgodnie z harmonogramem.

Cleanup jest celowany w state/tags/ARN zasobów pokazu:

1. Wstrzymaj CronJobs, workery i ruch, aby nie tworzyć nowych obiektów podczas cleanup.
2. Zachowaj wymagane evidence, manifests, modele/backupy z rollback policy w docelowym miejscu z retencją; sprawdź odczyt i checksum przed usunięciem źródła.
3. Przejrzyj plan destroy i potwierdź, że shared RetailOps VPC/subnets/state nie są objęte. Final snapshot RDS i deletion protection mają jawne ustawienie dla wybranego scenariusza.
4. Usuń własne zasoby zgodnie z dependency order, zwracając uwagę na LB, persistent volumes i inne zasoby utworzone przez kontrolery poza Terraform.
5. Sprawdź pozostałe S3 versions/delete markers, ECR images, snapshots, logs, secrets, endpoints/NAT/LB/EBS oraz zasoby w każdym użytym regionie. Nie usuwaj cudzych prefixów ani całych bucketów współdzielonych.
6. Porównaj inventory przed/po. Każda celowo pozostawiona pozycja ma ownera, koszt, retention i datę późniejszego cleanup. Po aktualizacji billing sprawdź koszt rzeczywisty i zanotuj opóźnienie.

`terraform destroy` zakończone kodem 0 nie jest samo w sobie dowodem zerowych kosztów ani braku pozostałości. W przypadku failure zachowaj stan i listę pozostałych zasobów, napraw uprawnienia/zależności oraz wykonaj ponownie tylko znany zakres.

## 9. Szablon ćwiczenia lub incydentu

```markdown
# <ID>: <scenariusz>
- Status: planned / exercised / verified
- Data, owner, środowisko:
- RetailOps SHA / AI SHA / release:
- Dataset / model / config / index / DB schema:
- Warunki początkowe i wpływ:
- Dokładne komendy:
- Oczekiwany wynik / wynik faktyczny:
- Detection: alert/log/trace:
- Containment:
- Recovery / rollback:
- Kontrola integralności i świeżości:
- Koszt i cleanup, jeśli dotyczy:
- Przyczyna / działanie zapobiegawcze:
- Linki evidence:
- Ograniczenia i niewykonane kroki:
```

Runbook pozostaje aktualny tylko wtedy, gdy zmiany endpointów, schematów, topics, tożsamości, release refs lub narzędzi są wprowadzane w nim w tym samym PR co kod i testy.
