# AI 09 — odbiór TensorFlow i konsolidacji portfolio

Zakres: zatwierdzony wariant 1 opisany w [planie etapu](../../../plans/ai/etapy/09-tensorflow-robustness.md).
Nowe porównanie dotyczy forecastingu; AI 07–08 zachowują odebrane historyczne
wyniki i ograniczenia. Warianty 2–3 są udokumentowanymi przyszłymi ulepszeniami.

## Wynik

Zamrożona decyzja: `reject_for_new_promotion_retain_existing_portfolio`.
TF odrzucono do nowej promocji; nie przełączono championa ani runtime.
Każdy z trzech seedów 42/137/2026 ma 19443 wspólne klucze sześciu metod
i 17437 kwalifikowanych etykiet. Wagi agregacji wynoszą po 1/3.
Bias średniej TF wynosi od −23,06% do −42,74%, przekraczając limit 10%.
Grupy historycznego wolumenu zero/high nie mają próbek i pozostają `not_ready`.
Ten wynik zamyka porównanie, bez kolejnej rundy strojenia lub promocji.

## Dowody zakresu

| Warunek | Dowód AI |
| --- | --- |
| R1: protokół i zamrożenie | [Protokół](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/72244a7f0f3f9377d28e61f138d161f7b9776241/docs/reference/ai09-portfolio-assessment-v1.json), [kalibracja i freeze](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/72244a7f0f3f9377d28e61f138d161f7b9776241/docs/evidence/09-134-portfolio-calibration-complete.json) |
| R2: oryginalne dane i wspólne klucze | [Lineage i trzy populacje](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/72244a7f0f3f9377d28e61f138d161f7b9776241/docs/evidence/09-136-portfolio-final-complete.json) |
| R3: rzeczywiste modele i stałe baseline | [Development](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/72244a7f0f3f9377d28e61f138d161f7b9776241/docs/evidence/09-132-portfolio-development-repair-complete.json) |
| R4: niezależne seedy i ustalone wagi | [Oryginalne raporty](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/tree/72244a7f0f3f9377d28e61f138d161f7b9776241/docs/evidence/09-final), [wykonanie final](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/actions/runs/38387579572) |
| R5: jakość, segmenty i ograniczenia | [Raport końcowy](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/72244a7f0f3f9377d28e61f138d161f7b9776241/docs/ai09-forecast-portfolio-report.md) |
| R6: artefakt TF, MLflow, CPU reload i koszty | [Karta modelu](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/72244a7f0f3f9377d28e61f138d161f7b9776241/docs/cards/tensorflow-portfolio.md) |
| R7: sprawdzone historyczne AI 07–08 | [Manifest konsolidacji](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/72244a7f0f3f9377d28e61f138d161f7b9776241/docs/evidence/09-128-historical-portfolio.json), [portfolio](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/blob/72244a7f0f3f9377d28e61f138d161f7b9776241/docs/ai09-consolidated-portfolio.md) |
| R8: raport, decyzja i publikacja | Dokładny odbiór PR/main opisany poniżej |

Trzy pełne archiwa final mają zweryfikowane rozmiary i SHA-256. Raporty,
predykcje i etykiety są zgodne z zawartością ZIP; niezależne obliczenie daje
dokładnie wszystkie oryginalne metryki i statusy segmentów. Pełne archiwa
zachowano prywatnie poza Git; zdalne artefakty Actions mają retencję 90 dni.
MLflow TF: `8431adeb9d024647a1d19ea01a4a2594`; model:
`model-sha256-d9747b63efb9136fa967951e0cf38ceb186d0922148bb21baf614ea73fcb8d73`.

Producent danych: Source `d2363a5c78e0b190132e5e3d804da73b3136487d`.
Nowy final wygenerowano po zamrożeniu modeli i kalibracji, poza znanym
wcześniejszym okresem. Nieznana część utraconej starszej historii dostępu
pozostaje nieznana. Jawna naprawa importu użyła tych samych źródeł;
ponownego dostępu nie przedstawiamy jako nowego nietkniętego testu.
Nie zmieniono modeli, kalibracji, segmentów ani polityk po final.

## Odbiór publikacji

**AI PR i wynikowy main odebrane: oba Required CI zakończone sukcesem 17/17.**
[Maszynowy zapis odbioru](ai-publication.json) zawiera dokładne rewizje, jobs
i kontrolę całej kolekcji testów. **AI 09 jest READY w wariancie 1 na
odebranym main Source**, po przyjęciu niniejszej dokumentacji zgodnie
z warunkiem publikacji poniżej.

| Odbiór | Dokładna rewizja | Required CI |
| --- | --- | --- |
| [AI PR #70](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/pull/70) | `23bb028312457ca569f2655e75d791b7adf86003` | [38404677738](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/actions/runs/38404677738): **success, 17/17 jobs** |
| AI main po scaleniu | [`72244a7f0f3f9377d28e61f138d161f7b9776241`](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/commit/72244a7f0f3f9377d28e61f138d161f7b9776241) | [38417346019](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/actions/runs/38417346019): **success, 17/17 jobs** |

W każdym z obu przebiegów cztery archiwa raportów CI mają zweryfikowane
SHA-256 i rozmiary. Cała kolekcja obejmuje 6062 testy: 6013 passed,
49 jawnych skipped, zero failures i errors. Cztery części mają pełne,
rozłączne pokrycie kolekcji. Wynikowy main ma identyczną zawartość jak
odebrany head PR i zaliczył własny pełny Required CI.

Warunek publikacji Source: niniejszy raport i zgodny plan są odbierane
przez dokładny Source PR i wynikowy main z zielonym Required CI. Status
READY obowiązuje na tym odebranym main, nie na samym roboczym branchu.
Dokumentacyjny zakres stosuje istniejące reguły wykrywania ścieżek; celowo
pominięte bramki spoza zakresu nie są opisywane jako passed. Przy spełnieniu
tego warunku R1–R8 są zamknięte i nie pozostaje dodatkowa kampania lub promocja
do wykonania w zatwierdzonym wariancie 1.

## Granice odbioru

- Brak nowej promocji produkcyjnej i odnowienia historycznych kapsuł serving.
- Dane syntetyczne i mały profil nie dowodzą działania na danych detalisty
  ani na pełnej skali `ai-training`.
- Zmienność trzech seedów jest opisowa; bootstrap przedziałów delty metryk
  pozostaje poza zatwierdzonym zakresem.
- AI 07–08 mają własne karty, polityki, dane i historyczne odbiory lifecycle.
  Konsolidacja nie jest nową wspólną kampanią trzech zastosowań.
- Pełny canonical capacity diagnostic, wariant 2 oraz wariant 3 nie są
  dodatkowymi warunkami zamknięcia zatwierdzonego wariantu 1.
