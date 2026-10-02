# Scenariusze anomalii biznesowych

Zakres AI 07.1a/07.1b: lokalny producent trzech scenariuszy popytu oraz
scenariuszy zwrotów i ograniczenia zapasu, z niezmiennym kandydatem i kontrolnym
przebiegiem bez injekcji. [Plan etapu](../plans/ai/etapy/07-anomalie-dq.md)
obejmuje następnie raw DQ, handoff i część modelową.
Kandydat nie jest source 2.7, snapshotem AI 03 ani odbiorem modelu.

## Kontrakt i proces

[Wykonywalny kontrakt](../../data/contracts/business_anomaly_plan.v1.schema.json)
ma wersję `business-anomaly-plan-1.0.0`; generator scenariuszy —
`business-anomaly-generator-1.0.0`. Plan należy do `simulation_truth`.
Każde okno wskazuje konkretny produkt, selling location i channel, włączne daty
UTC, ID, typ, stały mnożnik, zmieniane pola, seed i wersję generatora.

| Typ | Okno | Mnożnik |
|---|---|---|
| `one_day_spike` | Dokładnie jeden dzień | Większy od 1, najwyżej 20 |
| `multi_day_spike` | Co najmniej dwa dni | Większy od 1, najwyżej 20 |
| `sustained_drop` | Co najmniej trzy dni | Od 0 włącznie do 1 wyłącznie |

Mnożnik wchodzi do istniejącej formuły `daily_demand` **przed stochastic
rounding i podziałem budżetu na koszyki**. Noise, rounding draw, ceny,
promocje i pozostałe czynniki zachowują ten sam proces i seed. Transakcje
przechodzą następnie przez chronologiczną realizację AI 06, wspólny fizyczny
zapas i normalny proces zwrotów. Nie zwiększa się gotowych sales ani labeli.
Raport rozlicza latent, observed i lost units dla każdego okna. Przy braku
zapasu skok popytu może zwiększyć utracone sztuki bez skoku obserwowanej
sprzedaży; tego wyniku nie przedstawiamy jako wykrywalnego sales spike.

Nakładające się okna injekcji lub kontroli dla tego samego grain są odrzucane.
Okna muszą leżeć w historii oraz obejmować wyłącznie aktywne i otwarte
kombinacje. Każda injekcja wymaga kontrolnego okna `clean` tego samego grain,
co najmniej tej samej długości. Okno bez zmiany próbkowanego popytu jest
odrzucane jako nieskuteczna injekcja. `clean` nie może mieć zmienionego wyniku
inventory przez wcześniejsze injekcje lub wspólny zapas.

Pozostałe typy kontroli mają sprawdzaną semantykę: `promotion` musi mieć
rzeczywisty czynnik promocji, `seasonality` czynnik sezonowy lub tygodniowy,
a `insufficient_history` mniej wcześniejszych otwartych obserwacji niż jawny
próg planu. Wszystkie kontrolne czynniki popytu pozostają identyczne w obu
przebiegach. Raport osobno wskazuje, czy ich wynik inventory też jest taki sam;
skutków wspólnego zapasu nie maskuje się jako niezależnych czystych obserwacji.

## Zwroty i ograniczenie zapasu — 07.1b

[Osobny kontrakt fizyczny](../../data/contracts/business_physical_anomaly_plan.v1.schema.json)
ma wersję `business-physical-anomaly-plan-1.0.0`, a generator
`business-physical-anomaly-generator-1.0.0`. Nie rozszerza po cichu kontraktu
popytu v1; czytnik kandydata wybiera kontrakt na podstawie wersji planu.

| Typ | Zmieniany proces | Magnitude |
|---|---|---|
| `return_spike` | Prawdopodobieństwo wyboru rzeczywiście zakupionych sztuk do zwrotu, dla grain daty `returned_at` | Mnożnik większy od 1, najwyżej 20; wynikowe prawdopodobieństwo najwyżej 0,75 |
| `inventory_censored_episode` | Fizyczny zapas produktu we wskazanej stock location, bez zmiany latent demand | Całkowity cap 0–1000000 sztuk |

Zwroty zachowują deterministyczne potencjalne części zakupu, daty, statusy
i przyczyny. Nowe części mogą zostać wybrane wyłącznie w zadanym oknie;
łączna zwracana ilość nie przekracza rzeczywiście sprzedanej. Refundacja
i ewentualny restock wykonują normalny proces AI 06. Restock może zwiększyć
późniejszą realizację sprzedaży; raport nie przedstawia zwrotów jako procesu
niezależnego od zapasu.

Stock cap działa **przed każdym arrival korzystającym z tej samej fizycznej
puli** w oknie dat UTC. Nadmiar schodzi przez rzeczywisty ujemny `write_off`
w ledgerze, przed `sale_issue`; nowe przyjęcie/restock zostaje objęte cap przy
kolejnym arrival. Nie oznacza to ciągłego cap między zdarzeniami popytu.
Wszystkie kanały wspólnej puli realizują `min(latent, available)`. W facts
pozostają normalne ID zdarzeń i operacyjne ruchy, a powiązanie z injekcją jest
wyłącznie w truth. Raport wskazuje removed units i konkretne write-off IDs.

Plan fizyczny odrzuca kilka injekcji tego samego produktu, również w różnych
kanałach lub rozłącznych oknach: replenishment i zwroty mogą przenosić skutek
poza okno. Wymaga poprzedzającego `clean` tego samego grain i co najmniej tej
samej długości; porównuje jego wyniki inventory oraz zwroty w obu przebiegach.
Każdy epizod musi dać rzeczywisty wzrost zwracanych sztuk lub spadek observed
i wzrost lost units. `observed_sales_changes` rozlicza zmiany wszystkich grain
historii, także poza zakresem epizodu. Latent demand całej pary jest identyczny.

## Uruchomienie

Komendy zakładają root worktree oraz Python z zależnościami API/data.
W izolowanym worktree można wskazać istniejący venv głównego checkoutu:

```sh
PYTHON=/Users/oskarstachowski/retailops-cloud-native-platform/services/api/.venv/bin/python
"$PYTHON" -m data.anomalies.run --example --products 8 \
  --output-root data/generated/ai07-candidates \
  --output ci-cd/reports/data/ai07-demand.json

"$PYTHON" -m data.anomalies.run --physical-example --products 8 \
  --output-root data/generated/ai07-physical-candidates \
  --output ci-cd/reports/data/ai07-physical.json
```

`--example` wybiera deterministycznie aktywny grain z 30-dniową historią;
tworzy trzy epizody i cztery rodzaje kontroli. To jawna mała receptura
syntetyczna, wybierana przed istnieniem detektora. Nie jest reprezentatywnym
benchmarkiem ani selekcją na podstawie wyniku modelu.

`--physical-example` tworzy dwa epizody na różnych produktach oraz dwa
poprzedzające clean controls. Wybiera scope ze źródłowego przebiegu bez
injekcji: serię z największą sprzedażą dla zwrotów i późny rzeczywiście
zrealizowany arrival dla cap=0. To mała kontrola działania procesu, nie
reprezentatywny benchmark ani dobór scenariuszy do wyniku detektora.

Własny plan można przekazać przez `--plan /ścieżka/plan.json`, a konfigurację
zapasów przez `--inventory-config`. Obsługiwane CLI profiles to `ai-smoke`
i `ai-temporal-smoke`; seed planu i injekcji musi zgadzać się z `--seed`.
Runner odrzuca nominalną siatkę większą niż 5000 dziennych grain.
Receptura przykładowa wymaga co najmniej 30 dni. Pojedynczy artefakt ma limit
64 MiB. Pełne profile treningowe i performance acceptance nie należą do 07.1a/b.

## Artefakty i odczyt

Katalog `anomaly-candidate-sha256-…` zawiera wyłącznie:

| Ścieżka | Przeznaczenie |
|---|---|
| `scenario_manifest.json` | Format `anomaly-scenario-candidate-1.0.0`, identity, checksums, requested/resolved config, code/dependency provenance i jawne flagi false |
| `facts/commerce.json` | Fakty i plany źródła po wykonaniu procesu, bez labels i parametrów injekcji |
| `facts/inventory.json` | Operacyjny ledger, dostawy, realizacja sprzedaży/zwrotów, routing i reviews |
| `simulation_truth/anomaly_injections.json` | Osobny plan, epizody, porównanie ilości i okna kontrolne |
| `simulation_truth/process.json` | Parametry symulatora, prawda popytu i inventory, konfiguracja oraz reconciliation |

Identity wiąże efektywną konfigurację, plan, wszystkie artefakty, schema i kod;
lokalna ścieżka i commit provenance nie definiują ID. Powtórzenie zachowuje
identity i bajty danych. Zapis odbywa się w staging, po walidacji i ponownym
wykonaniu pary procesów publikuje się katalog przez rename. Istniejących
uszkodzonych kandydatów nie naprawia się ani nie nadpisuje.

`data.anomalies.candidate_io.read_candidate(path)` sprawdza allowlistę,
kanoniczny JSON, rozmiary, checksums, identity i provenance, a następnie
niezależnie powtarza generację obu procesów. Wykrywa także ponownie
zapieczętowaną zmianę samych etykiet lub faktów. Odtworzenie wymaga
zarejestrowanego kodu, zależności i wersji Pythona. `replay=False` sprawdza
jedynie strukturę/integralność i nie jest odbiorem semantyki procesu.

Feature projection pozostaje oparta na istniejącej allowliście faktów.
Truth nie jest wejściem feature buildera lub runtime API. Legacy
`anomalies.csv` i alerts nadal są precomputed outputs.

## Granica odbioru

Wszystkie kandydaty mają `source_ready=false`, `anomaly_ready=false` i
`model_ready=false`. Kontrolne porównanie generatora nie jest forecast expected
value dla modelu ani wynikiem detektora. Etapy AI 04/05 wymagają zgodnego
odbioru przed częścią modelową 07. Prace źródłowe AI 04 mają własny branch;
przed wspólnym nowym snapshotem trzeba uzgodnić ich wersję generatora.

Najbliższy zakres: raw DQ faults, offline replay/curation i wersjonowany handoff
AI 03. [Dowód 07.1b](../evidence/ai/07/07.1b/README.md) zapisuje wyniki zwrotów
i ograniczenia zapasu oraz zgodność z normalnymi ścieżkami generatora. Produkcyjne
projekcje, ACK i transportowe DLQ wyników należą do AI 10.
