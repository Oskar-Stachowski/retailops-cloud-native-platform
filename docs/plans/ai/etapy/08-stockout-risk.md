# 08 — Zbuduj model ryzyka stockout

**Repo:** AI. **Zależności:** 04, 05, 06. **Wynik:** skalibrowane ryzyko nowego stockout w kolejnych siedmiu dniach, z kolejką priorytetów i pełną lineage. Nie jest to automatyczne zamówienie towaru.

## Wejście i decyzje domenowe

Wymagane są inventory ledger/replenishment i uzgodnione lokalizacje z 06, ponownie zwalidowane features/evaluation po zmianie symulatora oraz lifecycle z 05. Korzystaj z [danych i czasu](../kontrakty/dane-i-czas.md), [bramek](../kontrakty/profile-i-bramki.md) oraz [ML/API](../kontrakty/ml-api-lifecycle.md).

Podstawowy grain to `product_id × stock_location_id × as_of`. Fizycznego wspólnego zapasu nie wolno niezależnie przypisać kilku kanałom, policzyć kilka razy i udawać niezależnych etykiet. Forecasty z kanałów/sklepów agreguj do lokalizacji przez mapowanie ważne w origin. Pole channel w ryzyku jest opcjonalne i dopuszczalne tylko przy rzeczywiście wydzielonym zapasie; prezentacyjny store/channel nie zastępuje klucza inventory. Nie mieszaj istniejącej heurystyki RetailOps `/inventory-risks` z modelowym prawdopodobieństwem.

## Małe PR-y

1. **Zdefiniuj label i eligibility.** W origin `t` przewiduj nowy stockout w `(t,t+7 dni]`, przy jawnej definicji stock measure i epizodu (np. dostępny zapas osiąga zero dla aktywnego asortymentu). Rozróżnij `on_hand`, reservations i dostępność; wybierz miarę zgodną z ledgerem zamiast zamiennie używać tych nazw. Etykieta 1 wymaga potwierdzonego zdarzenia w oknie. Etykieta 0 wymaga kompletnej obserwacji całego okna. Brak danych, wycofanie asortymentu lub cenzorowanie to `not_evaluable`, nie negatyw. `label_available_at` uwzględnia koniec okna i opóźnienia danych.
2. **Oddziel aktualne braki od nowego ryzyka.** Przy zerowym zapasie już w origin zwracaj `status=already_stockout`, bez pozornej prognozy nowego zdarzenia (`probability=null`). Takie przypadki są osobnym widokiem operacyjnym i nie wchodzą do zbioru incident-risk ani jego metryk. Opcjonalny model czasu do odzyskania zapasu to rozszerzenie, nie część tego kroku. Dodatni zapas przy niepełnej historii może otrzymać `insufficient_data`; status nie jest niskim ryzykiem.
3. **Zbuduj PIT feature dataset.** Cechy: aktualny znany zapas, ostatnia sprzedaż i jej zmienność, days of supply, historia stockout, otwarte replenishment, planowane daty dostaw i lead time znane w origin. Rzeczywista przyszła dostawa, supplier delay i przyszłe stany nie są features. Plan dostawy o przyszłym effective time jest dozwolony tylko jeśli jego wersja była dostępna przed origin. Nieznany/dawny zapas oznacz flagą i polityką staleness, nie zerem.
4. **Dodaj forecast jako bezpieczny upstream.** Wymagany jest co najmniej historyczny forecast baseline jako cecha oraz porównanie wariantu bez tej cechy. Historyczne forecast features powstają rolling-origin/cross-fitting. Zapisuj upstream model version, training cutoff, feature dataset, selection/config version oraz origin każdego wyniku. Parametry modelu, preprocessing i wybór hiperparametrów nie korzystają z późniejszych ocenianych outcomes. Artefakt może zostać fizycznie odtworzony dziś, ale jego granica wiedzy musi odpowiadać historycznemu cutoff. Model wytrenowany na całej przyszłej historii nie może wstecz uzupełniać features. Najprostszy poprawny wariant początkowy może użyć tylko baseline’u z historycznymi parametrami. Champion downstream może po porównaniu pominąć tę cechę; wykonanie i poprawność czasowa porównania pozostają częścią odbioru etapu.
5. **Zapisz politykę censored sales.** `observed_sales_units` z 04 nie jest estymatą latent demand. Days of supply zaniża ryzyko, gdy wyłącznie surowa sprzedaż ograniczona stockout służy za popyt. Dodaj jawne historyczne flagi/coverage i porównaj np. cechy sprzedaży z okresów dostępności versus zwykłe lagi. Każda korekta musi używać tylko informacji dostępnych w origin. Pokaż ablation i segment inventory-constrained; simulation latent demand służy jedynie osobnej diagnostyce, nie poprawianiu produkcyjnego wejścia.
6. **Zbuduj porównywalne modele.** Baseline: LogisticRegression z pełnym preprocessingiem (skalowanie numeryczne, ograniczone kategorie). Candidate: HistGradientBoostingClassifier. Próbkowanie, class weights i imputację fituj tylko w train. Jeśli stosujesz oversampling, kalibrację i ocenę rób przy naturalnej częstości zdarzeń, z ujawnioną polityką. Nie dodawaj kolejnej biblioteki wyłącznie dla nazwy w portfolio.
7. **Rozdziel train, tuning, calibration i test w czasie.** Okna predykcji przecinające boundary wymagają purge/gap oraz eligibility; reguła wynika z `label_available_at`, nie samej daty wiersza. Parametry dopasowuj na train/tuning; kalibrator sigmoid/isotonic na oddzielnym, czasowo późniejszym development calibration albo bezpiecznych out-of-fold predictions. Progi i capacity policy dobieraj na development outcomes. Final test nie jest używany do kalibracji ani wyboru threshold. Zbyt mała próba dla isotonic uzasadnia prostszy kalibrator lub odłożenie promocji, nie użycie testu.
8. **Oceń ranking, kalibrację i decyzję.** Raportuj PR-AUC z jawną konwencją (np. average precision), prevalence/no-skill reference, Brier, reliability curve, liczebności binów, ROC-AUC pomocniczo oraz recall@top-N/top-percent, precision i cost table dla ustalonej zdolności operatora. Np. N=20 to przykład polityki, a nie narzucona wartość. Raportuj kategorie/lokalizacje i coverage statusów. Gdy brak pozytywnych lub obu klas, właściwe metryki są `not_evaluable`; taki segment nie przechodzi wymaganej bramki jakości.
9. **Wersjonuj politykę ryzyka i serving.** Progi low/medium/high/critical oraz capacity są osobnym `threshold_version` powiązanym z modelem/kalibratorem i evidence. `probability` ma znaczenie tylko dla kwalifikujących się wierszy. Utrwal complete pipeline, model card, coefficient table/permutation importance i lokalne factual reason codes. Zarejestruj `retailops-stockout-risk`, przeprowadź reject/promote/rollback przez mechanizm05 i dodaj batch oraz stockout read/run endpoints. Agent nie może sam przestawiać progów ani promować modelu.

## Testy i failure cases

- Zdarzenie stockout dokładnie w origin jest current state; dokładnie na prawym końcu okna wchodzi do label zgodnie z kontraktem. Testuj granice timezone/DST.
- Niepełny siedmiodniowy tail nie tworzy etykiet 0. Zdarzenie spóźnione nie jest dostępne do historycznego treningu przed `available_at`.
- Ten sam SKU w dwóch lokalizacjach z różnym zapasem ma osobne etykiety. Dwa kanały wspólnej lokalizacji nie dublują popytu/zapasu.
- Przyszła rzeczywista dostawa nie zmienia cech origin; zmiana znanego planu po origin także nie zmienia ich wstecz.
- Upstream model fitted na danych późniejszych od cutoff powoduje błąd lineage gate. Późniejsze dane nie zmieniają dawnych forecast features.
- Stary inventory snapshot daje stale/insufficient_data, a nie current high/low risk. Zero już w origin nie zawyża metryk klasyfikatora.
- Kalibrator i threshold manifest wskazują wyłącznie development split. Final test access jest rejestrowany i ograniczony do zatwierdzonej kampanii.
- Model i policy mismatch blokuje run/promocję; poprzednie kompletne wyniki mogą być prezentowane wyłącznie z jawnym freshness.

## Artefakty i DoD

Label specification z przykładami, eligibility counts, feature availability table, inventory mapping, upstream forecast manifests, temporal splits, LR/HGB i calibration comparison, capacity/cost evidence, policy version, model card, MLflow entries oraz API examples.

**Gotowe, gdy:** dojrzałe etykiety wynikają z uzgodnionego ledgeru; current stockout i braki danych są odrębne; testy nie wykrywają leakage; prawdopodobieństwo jest ocenione pod kątem kalibracji; ranking i progi mają uzasadnienie na danych development. Odrzucenie HGB i wybór LR jest akceptowalnym wynikiem. Niewiarygodna jakość ma status blocked, a nie deklarację gotowego modelu.

## Prompt do Codex

```text
W repo retailops-ai-intelligence zrealizuj etap08 po04/05/06.
Najpierw sprawdź nowe dataset IDs i re-evaluation po zmianie symulatora06.
Zdefiniuj incident-stockout7d na product×physical stock_location i mature labels.
Oddziel already_stockout, censored oraz insufficient_data od negatywnych etykiet.
Wprowadź PIT features i temporal eligibility; forecast upstream wyłącznie rolling-origin
z historycznym training/selection cutoff. Nie używaj future delivery ani latent demand.
Porównaj LogisticRegression i HGB, kalibruj poza final test, wersjonuj threshold policy.
Pokaż ranking@capacity, Brier, PR-AUC convention, segmenty i coverage.
Podepnij wspólny MLflow/batch/API/lifecycle05. Wykonaj testy granic czasu,
lokalizacji, upstream lineage i stale data; zapisz evidence i realne komendy.
```
