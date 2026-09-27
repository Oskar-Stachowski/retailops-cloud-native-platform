# 04 — Zbuduj poprawny forecasting

**Repo:** AI. **Zależność:** 03. **Wynik:** powtarzalna prognoza obserwowanej sprzedaży z uczciwym porównaniem baseline’ów, RF i HistGradientBoosting. To kontrakt do wdrożenia; wskazane polecenia nie są deklaracją istniejącego CLI.

## Granica etapu

Pierwszy forecasting nie czeka na cały symulator inventory z 06. Jeżeli inventory nie spełnia jeszcze kontraktu czasu i lokalizacji, **całkowicie pomiń je w wersji features v1**. Nie zastępuj nieznanego zapasu zerem ani przyszłym snapshotem. Zapisz tę decyzję w model card i zamroź schemat cech dla wszystkich porównywanych modeli. Po 06 powstaje nowy dataset; ponów dotknięte porównania i dopiero wtedy dodawaj wersję v2 cech inventory.

Model prognozuje `target_type=observed_sales_units`, a nie nieograniczony popyt. Nazwa rejestru `retailops-demand-forecast` pozostaje nazwą techniczną. W raporcie i API wyjaśnij ograniczenie sprzedaży przez dostępny zapas; `latent_demand` jest wyłącznie truth do diagnostyki symulacji. Nie używaj dobrych wyników syntetycznych jako dowodu komercyjnej skuteczności.

## Wejście i kontrakty

- Zwalidowany immutable snapshot, curated manifest i jawna mapa aktywnego asortymentu z 03.
- [Dane i czas](../kontrakty/dane-i-czas.md): `available_at`, wersje korekt, waluty, jednostki, zero kontra brak i grain `business_date × product_id × store_id × channel`.
- [Profile i bramki](../kontrakty/profile-i-bramki.md): `ai-smoke` bada schemat/import; dopiero `ai-temporal-smoke` bada ścieżkę czasową. Wynik smoke nie jest bramką jakości modelu.
- [ML/API/lifecycle](../kontrakty/ml-api-lifecycle.md): wspólny run, metryki, identyfikatory i docelowy payload.

## Małe PR-y, w tej kolejności

1. **Zdefiniuj zadanie i kalendarz prognozy.** Wersjonowana konfiguracja zawiera grain, timezone kalendarza biznesowego (domyślnie UTC), cutoff dostępności, `forecast_origin`, `target_date`, listę horyzontów 1–14 oraz raportowane okna 7 i 14 dni. Domyślnie origin zamyka dzień biznesowy D w UTC, a `target_date=D+horizon_days` dla horyzontów 1–14; konkretny timestamp i politykę opóźnień zapisz w manifeście. Prognoza wystawiona raz na 14 dni nie może korzystać z później zaobserwowanej sprzedaży po drodze. Każdy origin ma tę samą granicę wiedzy dla wszystkich modeli.
2. **Zbuduj kalendarzowe features.** Reindeksuj tylko aktywne szeregi do pełnego kalendarza. Potwierdzony dzień bez sprzedaży ma zero; niepełna obserwacja ma status brakujących danych. Lagi 1/7/14/28 oznaczają dni kalendarzowe, a nie poprzednie dostępne wiersze. Dla direct forecast z origin zamykającym D przyjmij jawnie `origin_lag_k = sales[D+1-k]`; są to te same historyczne obserwacje dla horyzontów 1–14. Jeśli stosujesz lag względem target date, wartości po D są niedostępne i wymagają prognozy rekurencyjnej, nigdy rzeczywistych przyszłych sales. Rolling mean/std/count są przesunięte i używają wyłącznie historii dostępnej w origin. Dodaj kalendarz, jawne kategorie i cenę/promocję z planu znanego przed origin. Zakazane są cena ważona faktyczną sprzedażą z target day, jego stockout, zrealizowana dostawa, późniejsza korekta i przyszły inventory fallback.
3. **Wersjonuj feature i split manifests.** Feature allowlist, typy, preprocessing, brakujące wartości, minimalna historia i fallback/cold-start są kontraktem. `feature_set_id` obejmuje kod, efektywną konfigurację, parent dataset i treść; `split_id` obejmuje rzeczywiste granice i zasady kwalifikacji. Nie twórz ID wyłącznie z dat, profilu i seeda. Transformacje uczące parametry dopasowuj osobno na train każdego folda. Nie dopasowuj encoderów, imputacji ani skalowania na całym zbiorze.
4. **Zbuduj wspólny evaluator i baseline’y.** Zaimplementuj last observed, moving average z jawnym oknem kalendarzowym oraz seasonal naive lag 7; „same weekday last week” to ten sam baseline, nie niezależny model. Dla fixed-origin horyzontu 8–14 seasonal naive używa ostatniego dostępnego analogicznego dnia tygodnia, nie faktycznej sprzedaży z dni 1–7 po origin. Jawnie określ warianty rekurencyjne i obsługę braków. Baseline wybieraj na walidacji, nigdy na final test.
5. **Dodaj RF i HistGradientBoosting.** RF zapewnia ciągłość względem istniejącego RetailOps; HGB jest drugim kandydatem. Utrwal pełny pipeline preprocessing + model. Wspólny adapter zwraca identyczny grain, horyzonty i `target_type`. Dla forecastu wielohoryzontowego wybierz jawnie strategię direct (np. model per horizon albo horizon jako cecha), a jeśli używasz recursive, wszystkie wartości po origin muszą pochodzić z prognoz. Ogranicz grid, CPU, RAM i czas; raportuj zasoby. Istniejący batch RetailOps odczytuje oceniony artefakt RF i zachowuje jego decyzję dopuszczenia. Obecny wynik `rejected` pozwala na analizę diagnostyczną offline; serving i promocja do nowego lifecycle wymagają osobnego odbioru.
6. **Wykonaj chronological backtest.** Zdefiniuj expanding/rolling-origin train/validation, ewentualny gap dla dojrzałości etykiet oraz końcowy test. Train folda może korzystać tylko z etykiet dostępnych do jego training cutoff. Dane historyczne z wcześniejszego okresu mogą zasilać lagi późniejszych originów; zakazane jest wykorzystanie przyszłego outcome do dopasowania. W ramach każdego folda porównuj dokładnie te same originy/targety i politykę braków. Nie ukrywaj trudnych wierszy przez usunięcie ich tylko u jednego modelu.
7. **Dodaj metryki i niepewność.** WAPE, MAE, RMSE, bias, under/overforecast, liczebność i pokrycie licz globalnie, per horizon, kategoria, kanał i koszyk wolumenu. Po 06 dodaj segmenty constrained/unconstrained inventory. WAPE to suma błędów bezwzględnych / suma bezwzględnych obserwacji, nie średnia procentów. Gdy mianownik = 0, wynik jest `null/not_evaluable`; raportuj MAE i nadmiarowe prognozy na zerach. MAPE na dodatnich obserwacjach ma jawne pokrycie i nie stanowi głównej bramki. Przedziały z reszt kalibracyjnych/walidacyjnych mają nominalne coverage i ocenę empirical coverage/width; nie stroisz ich na final test.
8. **Zapisz evidence oraz minimalny lifecycle handoff.** Każdy run już teraz produkuje kompletny run manifest, config, predykcje, metryki, model card i checksumy. W 04 dopuszczalny jest plikowy artifact sink z tym samym interfejsem logowania. W 05 podepnij MLflow i przenieś/rejestruj artefakty z zachowaniem oryginalnego run ID i metadata; nie twórz drugiego silnika ewaluacji ani nie twierdź, że wcześniejszy trening wykonał się w MLflow. Eksperymentalny run nie jest automatycznie championem.

## Plan oceny, zanim zobaczysz final test

Konfiguracja z Git definiuje primary metric, minimalny delta względem wybranego baseline’u, limit bias, krytyczne segmenty, dopuszczalną regresję, minimalną próbę oraz budżet wykonania. Polityka braków i `not_evaluable` jest częścią gate. Brak wystarczającej próby w krytycznym segmencie oznacza `not_ready`, a nie zaliczenie. Kryteriów nie poluzowuje się po obejrzeniu testu.

Pierwsze 04/05 może używać wydzielonego development holdout. Zestaw portfolio i jego okno final test zostają zamrożone przed końcową kampanią 09. Nie używaj raz ujawnionego final test ponownie do wybierania cech, hiperparametrów czy modelu. Jeśli po błędzie metodologicznym potrzebna jest nowa ocena, wersjonuj protokół i wskaż nowy nietknięty holdout; starszy wynik jest development evidence, nie bezstronną oceną końcową.

## Testy i awarie do pokazania

- Dodanie sprzedaży, inventory, ceny lub korekty z `available_at > origin` nie zmienia dawnych features ani predykcji fixed-origin.
- Brak dnia kalendarzowego nie przesuwa znaczenia lag 7; dzień poza aktywnym asortymentem nie staje się sztucznym zerem.
- Dla `y=[0]`, `yhat=[100]`: MAE=100, WAPE=`null`, gate nie może zaliczyć modelu dzięki „WAPE=0”. Dla mieszanki zer i wartości dodatnich wszystkie obserwacje wchodzą do licznika WAPE.
- Baseline i RF/HGB mają identyczną listę ocenianych kluczy. Potencjalnie niemożliwy do oceny przypadek pozostaje w coverage report.
- Zmiana liczby produktów, feature allowlist albo granic splitu zmienia właściwe ID; identyczny rerun zachowuje content identity.
- Model trained after history na późniejszych etykietach nie może generować rzekomo historycznych features dla 08.
- Zbyt krótka historia daje jawne `insufficient_data` lub zatwierdzony baseline fallback, z metodą w output. Brak świeżych danych blokuje run; nie publikuje się częściowego wyniku jako sukcesu.

## Artefakty i DoD

Utrwal: konfigurację zadania, feature/split manifests, tabelę dostępności cech, raport leakage, wyniki baseline/RF/HGB, segment metrics, porównanie zasobów, przykładowe predykcje, model card i dokładne wykonane komendy. Korzystaj z [szablonów evidence](../szablony/karty-i-evidence.md).

**Gotowe, gdy:** ścieżka snapshot → features → time-aware evaluation jest powtarzalna; brak leakage potwierdzają testy negatywne; obsługa zer jest poprawna; słabszy kandydat może zostać odrzucony, a baseline pozostać championem. Wyższa złożoność nie jest celem akceptacji. Przekaż 05 zatwierdzony artefakt i pełną lineage.

## Prompt do Codex

```text
Pracujesz w repo retailops-ai-intelligence. Wykonaj etap 04 z niniejszego
pakietu w małych PR-ach. Najpierw przeczytaj kontrakty/dane-i-czas.md,
kontrakty/profile-i-bramki.md i kontrakty/ml-api-lifecycle.md oraz evidence03.
Potwierdź rzeczywiste CLI i pliki przed zmianami. Zamroź target observed_sales_units,
grain, origin/target i feature schema. Jeżeli 06 nie jest gotowe, pomiń inventory.
Zbuduj kalendarzowe PIT features, baseline'y, RF, HGB i jeden wspólny evaluator.
Wprowadź poprawne metryki zer, walidację dojrzałości etykiet i testy leakage.
Nie używaj simulation_truth jako features ani final test do strojenia.
Już teraz zapisuj pełny run contract przez artifact sink gotowy do MLflow w05.
Zakończ evidence: co uruchomiono, wyniki, ograniczenia, dokładne komendy,
ID i checksumy. Nie wdrażaj modeli ani zasobów cloud w tym etapie.
```
