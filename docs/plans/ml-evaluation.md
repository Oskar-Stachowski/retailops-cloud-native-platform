# Ocena ML i zasady dopuszczania modeli

**Status: do wykonania w istniejącym RetailOps. Aktualizacja dokumentacji: 27.09.2026.**

Celem jest świeży, odtwarzalny eksperyment ML, wiarygodne metryki i uzasadniona decyzja `candidate` albo `rejected`. Rzetelne odrzucenie modelu jest poprawnym wynikiem; nie wymaga dalszego strojenia w celu wymuszenia sukcesu.

Zacznij od protokołu oceny i kompletnego panelu kwalifikujących się serii. Obecny [kontrakt cech 2.0](../reference/ml-features.md) usuwa informacje niedostępne w jednodniowym origin, a [instrukcja ML](../guides/ml.md) opisuje tożsamość przebiegów. Kolejny trening oceniający jakość ma sens dopiero po sprawdzeniu granic czasu całego horyzontu. Wspólne docelowe wymagania opisują [dane i czas](ai/kontrakty/dane-i-czas.md), [profile i bramki](ai/kontrakty/profile-i-bramki.md) oraz [ML/API](ai/kontrakty/ml-api-lifecycle.md). Ten lokalny plan nie oznacza realizacji całego serwisu AI ani jego etapu 07.

## 1. Protokół oceny

- Zdefiniować osobno prognozę siedmiu dni z jednego origin i ewentualny eksperyment rolling one-step.
- Przygotować co najmniej trzy chronologiczne okna walidacyjne oraz końcowy odłożony test, niewykorzystywany do strojenia.
- Model i baseline oceniać na tych samych kwalifikujących się rekordach i z tą samą granicą dostępnej wiedzy.
- Zbudować pełny panel obowiązujących serii z jawną kompletnością źródeł; odróżnić zero obserwowane od braku zdarzeń, zamknięcia sklepu i nieaktywnego asortymentu. Nie zakładać zera bez dowodu dostępności i kompletności.
- Ustalić kalendarzowe lagi i okna; obecna implementacja liczy poprzednie obserwacje.
- Raportować pokrycie, pominięcia, daty, origin, horyzont i liczebności. Ustalić obsługę nowych produktów oraz niewystarczającej historii.

**Odbiór:** przebieg odpowiada planowanemu sposobowi użycia; nie ma losowego mieszania przyszłości z przeszłością ani aktualizowania zamrożonej prognozy późniejszymi actuals.

## 2. Kontrolowane treningi i analiza wyników

- Zacząć od `small`, kontrolować czas i pamięć; obecna wektoryzacja jest gęsta.
- Porównać uzgodnione warianty Random Forest ze średnią ruchomą i, przy wystarczającej historii, sezonowym modelem naiwnym.
- Raportować WAPE, MAE, RMSE, bias, wyniki per okno oraz istotne kategorie/sklepy/kanały i liczebność segmentów.
- Powtórzyć eksperyment w odtworzonym środowisku i porównać prognozy w ustalonej tolerancji.
- Wyjaśnić różnice względem starego snapshotu. Po zmianie danych lub protokołu nie przedstawiać różnicy metryk jako czystego wpływu nowego modelu.

**Odbiór:** świeży raport, porównywalne warianty, odtworzony wynik oraz jawne ograniczenia danych syntetycznych.

## 3. Polityka dopuszczenia

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

## 4. Użycie dokładnie ocenionego artefaktu

- Spiąć minimalną ścieżkę lokalną: zapis modelu → odczyt → batch predictions → metadata → raport metryk.
- Każdy wynik ma wskazywać ten sam model, dataset i eksperyment. Wykluczyć ciche przełączenie na baseline lub niejawny retraining.
- Sprawdzić zgodność prognoz z kontraktem API, unikalność kluczy i poprawność wartości oraz ograniczenia statusów.
- Weryfikować zgodność prognoz przed i po zapisie. Odczyt wykonywać w zgodnym, zapisanym środowisku zależności; nie zakładać zgodności historycznych binariów z nową wersją scikit-learn.
- Sam plik `.prom` nie oznacza rzeczywistego zbierania metryk przez Prometheus. Opisać zakres dowodu zgodnie z tym, co faktycznie uruchomiono.

**Odbiór:** odczytany model jest dokładnie ocenionym artefaktem, a prognozy i metryki mają spójne pochodzenie.

## 5. CI, dowody i aktualizacja main

- Dodać małą deterministyczną kontrolę do CI i znaczące testy negatywne: leakage, pusta ocena, niezgodna identity, obejście blokady promocji.
- Pełniejszą ocenę zapisywać jako osobny przebieg z artefaktami.
- Umieścić nowy datowany raport w `docs/evidence/ml/<nowa-wersja>/`; zachować historyczny snapshot.
- Raport powinien zawierać konfigurację, środowisko, metryki, prognozy, sumy kontrolne, kartę modelu, decyzję i ograniczenia. Duże generowane dane pozostają poza Git zgodnie z polityką projektu.
- Zaktualizować dokumentację ML i indeks dowodów, a wykonany zakres usunąć z aktywnego planu; zmiany przeprowadzić przez PR i wymagane kontrole do `main`.

**Odbiór planu:** wiarygodny i odtwarzalny wynik, działająca polityka decyzji, spójna ścieżka artefaktu oraz dowody na main. Wynik `rejected` nie wymaga bezterminowego strojenia w celu wymuszenia sukcesu modelu.

## Powiązanie z rozbudową AI

Po odbiorze porównaj wynik z [etapem AI 00](ai/etapy/00-audyt.md) i rozpocznij zależności [mapy AI](ai/README.md). Poprawki dostępności cech, czasu i ewaluacji mają służyć obu pracom. Pełny ledger, Helm, MLOps i wdrożenie chmurowe mają osobne zakresy i nie wynikają z samego wykonania tego planu.
