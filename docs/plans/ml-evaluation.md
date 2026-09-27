# Ocena ML i zasady dopuszczania modeli

**Status: do wykonania w istniejącym RetailOps. Aktualizacja dokumentacji: 27.09.2026.**

Celem jest świeży, odtwarzalny eksperyment ML, wiarygodne metryki i uzasadniona decyzja `candidate` albo `rejected`. Rzetelne odrzucenie modelu jest poprawnym wynikiem; nie wymaga dalszego strojenia w celu wymuszenia sukcesu.

Zacznij od tożsamości eksperymentu, dostępności cech w chwili prognozy i protokołu oceny (punkty 1–3). Kolejny trening ma sens dopiero po sprawdzeniu tych granic. Wspólne docelowe wymagania opisują [dane i czas](ai/kontrakty/dane-i-czas.md), [profile i bramki](ai/kontrakty/profile-i-bramki.md) oraz [ML/API](ai/kontrakty/ml-api-lifecycle.md). Ten lokalny plan nie oznacza realizacji całego serwisu AI ani jego etapu 07.

## 1. Punkt odniesienia i tożsamość eksperymentu

- Zapisać commit/stan kodu, konfigurację danych i generatora, zakres dat, seed, parametry modelu, wersję kontraktu oraz wersje Pythona i zależności.
- Nadać nowemu przebiegowi i modelowi osobną tożsamość. Zachować historyczny katalog `random-forest-v1`.
- Rozdzielić odtworzenie konfiguracji 20 drzew, wpływ poprawek cech/protokołu i wariant 80 drzew. Starego protokołu nie używać do dopuszczenia nowego modelu.
- Zapisać polecenie odtworzenia i sumy kontrolne; rozróżnić integralność bajtów artefaktu od powtarzalności logicznych danych i prognoz.

**Odbiór:** inna osoba potrafi odtworzyć warunki eksperymentu i przypisać każdy wynik do kodu, danych i środowiska.

## 2. Dostępność cech i kontrakt danych

- Ustalić origin prognozy oraz dostępność każdego źródła w tym momencie.
- Zrealizowaną cenę przyszłego dnia zastąpić zatwierdzoną ceną planowaną znaną w origin albo wyłączyć cechę. Tak samo rozliczyć promocje i stockout.
- Wyłączyć cechy zapasu, które nie spełniają kontraktu. Pakiet AI przewiduje pierwszy forecasting bez takich cech do czasu wiarygodnego ledgeru; nie rozszerzać automatycznie tego zadania na budowę całego ledgeru.
- Usunąć fallback do przyszłego snapshotu i sprawdzić poprawność lokalizacji zapasu.
- Rozróżnić zerową sprzedaż, brak danych, zamknięcie sklepu i nieaktywny asortyment. Ustalić kalendarzowe lagi oraz okna.
- Zachować granicę między obserwowanymi faktami a prawdą symulatora; latentny popyt i etykiety nie trafiają do cech runtime.
- Dodać testy: zmiana faktów dostępnych po origin nie zmienia cech ani zamrożonej prognozy; brak historii nie powoduje użycia przyszłości.

**Odbiór:** jawny kontrakt dostępności, testy granic czasu i brak użycia przyszłych outcomes. Target to obserwowana sprzedaż; nie deklarować prognozy niezaspokojonego popytu.

## 3. Protokół oceny

- Zdefiniować osobno prognozę siedmiu dni z jednego origin i ewentualny eksperyment rolling one-step.
- Przygotować co najmniej trzy chronologiczne okna walidacyjne oraz końcowy odłożony test, niewykorzystywany do strojenia.
- Model i baseline oceniać na tych samych kwalifikujących się rekordach i z tą samą granicą dostępnej wiedzy.
- Raportować pokrycie, pominięcia, daty, origin, horyzont i liczebności. Ustalić obsługę nowych produktów oraz niewystarczającej historii.

**Odbiór:** przebieg odpowiada planowanemu sposobowi użycia; nie ma losowego mieszania przyszłości z przeszłością ani aktualizowania zamrożonej prognozy późniejszymi actuals.

## 4. Kontrolowane treningi i analiza wyników

- Zacząć od `small`, kontrolować czas i pamięć; obecna wektoryzacja jest gęsta.
- Porównać uzgodnione warianty Random Forest ze średnią ruchomą i, przy wystarczającej historii, sezonowym modelem naiwnym.
- Raportować WAPE, MAE, RMSE, bias, wyniki per okno oraz istotne kategorie/sklepy/kanały i liczebność segmentów.
- Powtórzyć eksperyment w odtworzonym środowisku i porównać prognozy w ustalonej tolerancji.
- Wyjaśnić różnice względem starego snapshotu. Po zmianie danych lub protokołu nie przedstawiać różnicy metryk jako czystego wpływu nowego modelu.

**Odbiór:** świeży raport, porównywalne warianty, odtworzony wynik oraz jawne ograniczenia danych syntetycznych.

## 5. Polityka dopuszczenia

Poniższe liczby są **propozycją do oceny przed eksperymentem, nie zatwierdzoną polityką ani istniejącą implementacją**. Przed eksperymentem skonfrontować je z [kontraktami profili i bramek AI](ai/kontrakty/profile-i-bramki.md), zapisać politykę właściwą dla lokalnego kroku i rozstrzygnąć różnice. Nie zmieniać progów po zobaczeniu wyniku.

| Warunek | Propozycja |
|---|---|
| Dane i czas | Kontrakt spełniony, brak leakage i duplikatów |
| Pokrycie | Wynik dla wszystkich kwalifikujących się rekordów; pominięcia z uzasadnieniem |
| Jakość | WAPE co najmniej 5% względnie lepsze od ustalonego baseline na końcowym teście |
| Stabilność | Przewaga w co najmniej dwóch z trzech okien walidacyjnych |
| Segmenty | MAE nie gorsze o więcej niż 5% w wcześniej wybranych segmentach o ustalonej minimalnej liczebności |
| Reprodukcja | Zgodne wyniki powtórzenia oraz test zapisu/odczytu modelu |
| Drift | `failed` blokuje; `warning` wymaga jawnego uzasadnienia dalszej decyzji |

- Zapisać decyzję i wynik każdego warunku w formacie maszynowym.
- Brak ocenialnych danych, zerowy mianownik i nieprawidłowe metryki oznaczają brak podstaw do pozytywnej decyzji, nie idealny wynik.
- Ustalić granicę statusów: `candidate` dopuszcza dalszą lokalną walidację; nie oznacza produkcyjnej gotowości.
- Proste kontrole driftu na syntetycznych seedach potwierdzają mechanizm kontroli; nie dowodzą odporności na rzeczywisty drift produkcyjny.

**Odbiór:** decyzja `candidate`/`rejected` ma odtwarzalne uzasadnienie i nie daje się obejść samym ręcznym ustawieniem statusu w ścieżce dopuszczonych modeli.

## 6. Użycie dokładnie ocenionego artefaktu

- Spiąć minimalną ścieżkę lokalną: zapis modelu → odczyt → batch predictions → metadata → raport metryk.
- Każdy wynik ma wskazywać ten sam model, dataset i eksperyment. Wykluczyć ciche przełączenie na baseline lub niejawny retraining.
- Sprawdzić zgodność prognoz z kontraktem API, unikalność kluczy i poprawność wartości oraz ograniczenia statusów.
- Weryfikować zgodność prognoz przed i po zapisie. Odczyt wykonywać w zgodnym, zapisanym środowisku zależności; nie zakładać zgodności historycznych binariów z nową wersją scikit-learn.
- Sam plik `.prom` nie oznacza rzeczywistego zbierania metryk przez Prometheus. Opisać zakres dowodu zgodnie z tym, co faktycznie uruchomiono.

**Odbiór:** odczytany model jest dokładnie ocenionym artefaktem, a prognozy i metryki mają spójne pochodzenie.

## 7. CI, dowody i aktualizacja main

- Dodać małą deterministyczną kontrolę do CI i znaczące testy negatywne: leakage, pusta ocena, niezgodna identity, obejście blokady promocji.
- Pełniejszą ocenę zapisywać jako osobny przebieg z artefaktami.
- Umieścić nowy datowany raport w `docs/evidence/ml/<nowa-wersja>/`; zachować historyczny snapshot.
- Raport powinien zawierać konfigurację, środowisko, metryki, prognozy, sumy kontrolne, kartę modelu, decyzję i ograniczenia. Duże generowane dane pozostają poza Git zgodnie z polityką projektu.
- Zaktualizować dokumentację ML i indeks dowodów, a wykonany zakres usunąć z aktywnego planu; zmiany przeprowadzić przez PR i wymagane kontrole do `main`.

**Odbiór planu:** wiarygodny i odtwarzalny wynik, działająca polityka decyzji, spójna ścieżka artefaktu oraz dowody na main. Wynik `rejected` nie wymaga bezterminowego strojenia w celu wymuszenia sukcesu modelu.

## Powiązanie z rozbudową AI

Po odbiorze porównaj wynik z [etapem AI 00](ai/etapy/00-audyt.md) i rozpocznij zależności [mapy AI](ai/README.md). Poprawki dostępności cech, czasu i ewaluacji mają służyć obu pracom. Pełny ledger, Helm, MLOps i wdrożenie chmurowe mają osobne zakresy i nie wynikają z samego wykonania tego planu.
