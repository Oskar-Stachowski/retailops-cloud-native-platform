# Ocena ML i zasady dopuszczania modeli

**Status: do wykonania w istniejącym RetailOps. Aktualizacja dokumentacji: 27.09.2026.**

Celem jest świeży, odtwarzalny eksperyment ML, wiarygodne metryki i uzasadniona decyzja `candidate` albo `rejected`. Rzetelne odrzucenie modelu jest poprawnym wynikiem; nie wymaga dalszego strojenia w celu wymuszenia sukcesu.

Obecny [kontrakt cech 2.0](../reference/ml-features.md) wyłącza informacje niedostępne w origin, a [instrukcja ML](../guides/ml.md) opisuje tożsamość przebiegów, poprawne metryki, ocenę całego horyzontu na syntetycznym panelu oraz użycie tego samego ocenionego artefaktu w batchu, metadanych i raporcie metryk. [Lokalna polityka dopuszczenia](../reference/ml-admission-policy.md) określa sprawdzaną decyzję RF. Dalsza praca dotyczy świeżego odbioru eksperymentu. Wspólne docelowe wymagania opisują [dane i czas](ai/kontrakty/dane-i-czas.md), [profile i bramki](ai/kontrakty/profile-i-bramki.md) oraz [ML/API](ai/kontrakty/ml-api-lifecycle.md). Ten lokalny plan nie oznacza realizacji całego serwisu AI ani jego etapu 07.

## 1. Kontrolowane treningi i analiza wyników

- Zacząć od `small`, kontrolować czas i pamięć; obecna wektoryzacja jest gęsta.
- Porównać uzgodnione warianty Random Forest ze średnią ruchomą i, przy wystarczającej historii, sezonowym modelem naiwnym.
- Raportować WAPE, MAE, RMSE, bias, wyniki per okno oraz istotne kategorie/sklepy/kanały i liczebność segmentów.
- Powtórzyć eksperyment w odtworzonym środowisku i porównać prognozy w ustalonej tolerancji.
- Wyjaśnić różnice względem starego snapshotu. Po zmianie danych lub protokołu nie przedstawiać różnicy metryk jako czystego wpływu nowego modelu.

**Odbiór:** świeży raport, porównywalne warianty, odtworzony wynik oraz jawne ograniczenia danych syntetycznych.

## 2. CI, dowody i aktualizacja main

- Dodać małą deterministyczną kontrolę do CI i znaczące testy negatywne: leakage, pusta ocena, niezgodna identity, obejście blokady promocji.
- Pełniejszą ocenę zapisywać jako osobny przebieg z artefaktami.
- Umieścić nowy datowany raport w `docs/evidence/ml/<nowa-wersja>/`; zachować historyczny snapshot.
- Raport powinien zawierać konfigurację, środowisko, metryki, prognozy, sumy kontrolne, kartę modelu, decyzję i ograniczenia. Duże generowane dane pozostają poza Git zgodnie z polityką projektu.
- Zaktualizować dokumentację ML i indeks dowodów, a wykonany zakres usunąć z aktywnego planu; zmiany przeprowadzić przez PR i wymagane kontrole do `main`.

**Odbiór planu:** wiarygodny i odtwarzalny wynik, działająca polityka decyzji oraz dowody na main. Wynik `rejected` nie wymaga bezterminowego strojenia w celu wymuszenia sukcesu modelu.

## Powiązanie z rozbudową AI

Po odbiorze porównaj wynik z [etapem AI 00](ai/etapy/00-audyt.md) i rozpocznij zależności [mapy AI](ai/README.md). Poprawki dostępności cech, czasu i ewaluacji mają służyć obu pracom. Pełny ledger, Helm, MLOps i wdrożenie chmurowe mają osobne zakresy i nie wynikają z samego wykonania tego planu.
