# 09 — Porównaj TensorFlow i zamknij ewaluację ML

**Repo:** AI. **Zależności:** 07 i 08 (pośrednio 04/05/06). **Wynik:** końcowa, porównywalna ocena wszystkich trzech zastosowań i rzeczywisty TensorFlow challenger dla forecastingu. Challenger jest wymagany w pełnym lokalnym portfolio; jego promocja na championa nie jest wymagana.

## Przed rozpoczęciem kampanii

Sprawdź, że wyniki po 06 pochodzą z aktualnego ledgeru/symulatora i mają nowe właściwe source/curated/feature IDs. Nie porównuj jednego modelu na starej generacji bez ograniczeń zapasu z innym na nowej. Zamroź wersje generatora, kontraktów, schematów features, kalibracji, progów, splitów, metric implementation i listę scenariuszy w protokole oceny.

Profile i seeds określa [kontrakt bramek](../kontrakty/profile-i-bramki.md): końcowy zestaw **[42, 137, 2026]** jest ustalony przed oceną; każdy seed raportuj osobno i łącznie. Nie regeneruj scenariusza z nowym seedem, ponieważ challenger przegrał. Oddziel seed danych od seeda inicjalizacji/treningu. Manifest zawiera oba.

## Małe PR-y

1. **Zbuduj kompaktowy model Keras.** Okno historyczne, wyraźnie opisane encoding/embeddings, małe dense layers i direct multi-horizon output 1–14. LSTM/Transformer nie jest wymagany. Kategorie nieznane mają kontrolowany fallback; skalowanie, imputacja i embedding vocabulary są fitowane tylko na train folda. Early stopping korzysta z development validation. Model ma limit CPU/RAM/czasu i locked dependencies. Determinism włącz tam, gdzie wspierany; zapisz platformę i ewentualną niedeterministyczność.
2. **Podepnij wspólny kontrakt.** TensorFlow korzysta z tych samych źródeł, originów/targetów, dostępności features i zbioru ocenianych obserwacji co RF/HGB/baseline. Różnica reprezentacji wejścia może być uzasadniona architekturą, ale żaden model nie dostaje późniejszych danych. Zapisz preprocessing i podpis wejścia razem z modelem przez wspierany MLflow flavor/format. Typed wrapper zwraca ten sam output. Testuj ładowanie artefaktu na docelowym CPU, nie tylko w notebooku.
3. **Dokończ strojenie na development.** Budżet prób i kryterium wyboru zamroź przed uruchomieniem. Nie dawaj TensorFlow nieograniczonego wyszukiwania i nie porównuj go z celowo niedostrojonym baseline’em. Rejestruj każdą próbę, koszt, seed i odrzucenie. TF może przegrać; wartościowy wynik portfolio to uczciwe wyjaśnienie trade-off, np. zbliżony WAPE przy większym koszcie.
4. **Zamknij polityki trzech zastosowań.** Forecast: metric+coverage+bias/interval gates. Anomaly: per observation i per episode, tolerancja detekcji, deduplikacja alertów, clean controls, false alerts/1000 oraz no-positive handling zgodnie z07. Stockout: mature-label eligibility, calibration i threshold/capacity zgodnie z08. Karty modeli identyfikują poziom oceny i ograniczenia. Reguły, kalibratory i przedziały muszą być zamrożone przed final test.
5. **Wykonaj zatwierdzoną końcową ocenę.** Na każdym seedzie odtwórz identyczny pipeline source → snapshot → curated → features → chronological evaluation. Train i development poprzedzają final test. Test służy potwierdzeniu wcześniej wybranego kandydata i hard gates, nie nowej rundzie wyboru architektury. Jeżeli final test odrzuca kandydata, zachowaj zatwierdzony baseline/championa; dalsze strojenie wymaga nowego protokołu i nowego nietkniętego holdout. Repeated test access jest widoczny w evidence.
6. **Dodaj robustness i segmenty.** Wersjonowane scenariusze obejmują zero/intermittent sales, cold start, kategorie/wolumeny/kanały, brakujące/spóźnione dane, znane promocje, inventory constraints, zmienny lead time i zaplanowane anomalie. Scenario labels nie są wejściem modelu. Różnice raportuj wraz z n, coverage, prevalence i ważnością metryk. Wagi agregacji ustal przed wynikami; nie ukrywaj słabszego seeda przez pooling. Wymagane krytyczne segmenty z za małą próbą blokują promocję do czasu zebrania poprawnej oceny.
7. **Oceń niepewność i koszty.** Pokaż różnicę wyników na tych samych predykowanych kluczach, zmienność między seedami i ostrożną interpretację. Jeśli wyznaczasz przedziały dla delty metryk, resampling respektuje zależność czasu/serii (np. blokowy/klastrowy), a nie losuje niezależnych sąsiednich dni. Mierz training time, peak memory, artifact size, cold load i batch inference. Nie wymagaj statystycznej istotności pozornej próby traktującej wszystkie wiersze jako niezależne.
8. **Podejmij i utrwal decyzje lifecycle.** W MLflow wszystkie trzy zastosowania mają baseline i candidate evidence; TensorFlow ma własny run/model artifact i dokumentowany wynik. Champion dla każdego zastosowania przechodzi te same gates, review i runtime smoke. Wersję modelu, preprocessing, kalibrację, threshold i feature schema przypinaj jako kompatybilny pakiet. Odrzucone wyniki pozostają w rejestrze/artifact store; nie nadpisuj raportu pokazującego porażkę.

## Wymagane testy i awarie

- Zmieniona future observation nie wpływa na historyczny window TF. Normalizer/encoder nie zawiera kategorii/parametrów wyuczonych na test.
- Ten sam split daje te same oceniane klucze w baseline/RF/HGB/TF; padding lub okno TF nie powoduje cichego wyboru łatwiejszych obserwacji.
- Model po reload daje zgodne wyniki w zadeklarowanej tolerancji numerycznej; brak wsparcia na docelowej architekturze blokuje jego release.
- Test `all-zero`, brak pozytywnych anomalii/stockout, mała próbka i stale label window nie są raportowane jako idealne metryki.
- Negatywny wynik gate odrzuca kandydata bez przestawienia runtime. Brak artefaktu lub checksum/signature mismatch blokuje publikację.
- Promocja starszego feature schema nie może po cichu konsumować nowego curated/feature payloadu.

## Artefakty i DoD

Zamrożony evaluation protocol, lista danych/seedów/scenariuszy, per-seed i pooled metrics z wagami, segment gates, raport RF/HGB/TF/baseline, trzy model cards i evaluation reports, TF artifact i environment, lineage, audyt decyzji, tabelka koszt/jakość i właściwe runbooki [ML/API/lifecycle](../kontrakty/ml-api-lifecycle.md).

**Gotowe, gdy:** TensorFlow rzeczywiście trenowano, odtworzono i oceniono; trzy zastosowania mają pełną evidence na uzgodnionych danych; najlepsza kwalifikująca się konfiguracja została wybrana zgodnie z protokołem; niedostateczne wyniki i ograniczenia nie są ukryte. Etap09 zamyka część porównawczą ML. Pełny lokalny odbiór nadal wymaga integracji/agenta, observability, kind/Helm i CI/GitOps; pełny zakres v1 także części AWS i końcowego odbioru zgodnie z mapą.

## Prompt do Codex

```text
W repo retailops-ai-intelligence wykonaj etap09 po07/08.
Przeczytaj profile-i-bramki, dane-i-czas i ml-api-lifecycle. Sprawdź lineage po06.
Zamroź protokół, seeds danych [42,137,2026], splity, scenariusze i gates przed testem.
Dodaj kompaktowy Keras multi-horizon challenger CPU z pełnym preprocessingiem
i MLflow artifact. Korzystaj z tego samego evaluator/origin/target co baseline/RF/HGB.
Strojenie, early stopping, calibration i thresholds wykonuj tylko na development.
Porównaj trzy use case'y na seedach/segmentach z coverage i nieokreślonymi metrykami.
Zapisz koszt i robustness; nie promuj TensorFlow tylko dlatego, że jest bardziej złożony.
Pokaż reject/promote oraz reload smoke. Oddziel wykonane wyniki od założeń.
Final test nie jest nową pętlą strojenia; utrwal dostęp i decyzje w evidence.
```
