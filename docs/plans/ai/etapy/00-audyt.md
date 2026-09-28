# 00 — Ustal stan wyjściowy

**Repo:** RetailOps; także AI, jeśli jest dostępne. **Zależności:** brak.

Aktualny wynik: [audyt z 27.09.2026 na `cbf28b2`](../../../evidence/ai/00/README.md).
Następny krok: **[01 — fundament](01-fundament-projektu.md)**; [backlog](../backlog.md)
podaje otwarte warunki i pierwsze małe PR-y. Poniżej pozostaje procedura
ponownego audytu po zmianie źródeł, nie lista prac oczekujących w etapie 00.

## Cel

Potwierdź, które zadania są nadal potrzebne, na aktualnym commicie i bez nadpisywania wcześniejszej pracy. Uwzględnij [lokalną ocenę ML](../../../evidence/ml/fixed-origin-rf-2026-09-27/README.md) i jej ograniczenia. Wyniki i wykonane polecenia są w raporcie; poniższe wymagania służą powtórzeniu audytu na nowej rewizji.

## Procedura ponownego audytu

1. **Inwentaryzacja.** Zapisz branch, SHA, working-tree status, lokalne instrukcje i istniejące PR-y. Przeczytaj Makefile, generator, `ml/`, API, event registry/consumer, wymagane CI oraz entry point Terraform. Oddziel istniejący runtime od opisów planowanych.
2. **Reprodukcja danych.** Uruchom mały deterministyczny profil dwukrotnie do różnych katalogów tymczasowych. Zapisz parametry efektywne, wersje środowiska, row counts i checksums. Nie nadpisuj `data/demo` ani commitowanych fixtures.
3. **Reprodukcja błędów ML i generatora.** Sprawdź zakresy poniżej oraz pipeline wejść każdego modelu. Nie traktuj samego time split jako dowodu braku leakage.
4. **Reprodukcja kontraktów.** Porównaj event registry, publikowane envelope, router i walidację konsumenta, topic init i faktyczne pola API. Przejrzyj ACK/DLQ oraz projekcje wyników AI.
5. **Raport i backlog.** Utrwal wyniki w małym pliku evidence, przypisz potwierdzone otwarte problemy do etapów 02–16. Problemy już naprawione usuń z aktywnej listy; nie odtwarzaj ich przez cofnięcie kodu i nie pozostawiaj wpisów „rozwiązane”.

## Zakres kontroli przy powtórzeniu

| Kontrola | Co sprawdzić | Etap powiązany |
|---|---|---|
| Daily panel | Pełna siatka ważnych kombinacji, jawne zera, osobne missing/closed/inactive | 02–04 |
| Calendar lags | Lagi i okna liczone po datach, również przy lukach | 04 |
| Inventory | Brak przyszłych snapshotów i prawidłowe mapowanie lokalizacji | 02, 04, 06 |
| Cechy ceny i stockout | Dostępność każdej używanej wartości przed origin | 04 |
| Metryki zer i braków | Zerowy mianownik lub brak próby nie daje idealnego wyniku | 04 |
| Identity | Zmiana danych/parametrów zmienia odpowiednią tożsamość | 03 |
| Chronologia | Zamówienie przed sprzedażą, zwrot po sprzedaży | 02 |
| Koszyki | Powtórzenia SKU, ilości i sumy uzgodnione z transakcjami | 02 |
| Ceny/promocje | Coverage, scope, wersje i zgodność flag z transakcjami | 02 |
| Zakres dat | Manifest poprawnie opisuje zwroty, plany cen, tail i watermark | 02–03 |
| Inventory movements | Otwarcie nie jest dodawane ponownie przy snapshotach | 06 |
| Event schema | Zgodność registry, generatora, topic init i konsumenta | 10 |
| ACK i DLQ | Offset zatwierdzony dopiero po trwałym skutku lub kwarantannie | 10 |
| Projekcje | Wynik AI dostępny przez domenowy read model | 10 |

Mianownik panelu obejmuje wyłącznie poprawne pary location/channel i aktywne daty. Determinizm nie dowodzi poprawności tożsamości danych. Sprawdź oddzielnie tożsamość modelu w treningu, zapisie i batch inference, aktualne OpenAPI i paginację, granicę demo auth oraz właściwy entry point `infra/environments/dev/`.

## Warunek odbioru

Raport zawiera SHA, konfigurację, polecenia, wyniki i ograniczenia; testy wykonane są oddzielone od analizy statycznej. Oznaczono prawdziwe blokery per zastosowanie, bez uzależniania całego forecastingu od kompletnego procurement. Znany jest zakres pierwszego PR-u etapu 01/02.

Nie wymagamy uruchomienia AWS ani pełnego klastra do zaliczenia tego audytu. Jeżeli źródła/środowisko blokują wykonanie generatora, zapisz blokadę i nie oznaczaj pomiarów jako wykonanych.

## Prompt

```text
Wykonaj etap 00 z pakietu instrukcji RetailOps. To audyt aktualnego stanu.
Zapisz SHA i warunki środowiska, wygeneruj small dwukrotnie w temp, zmierz
kompletność panelu, semantykę lagów, leakage, ceny/promo, chronologię,
identity collision i zachowanie metryk przy zerach. Zweryfikuj actual API,
event registry/routing/ACK/DLQ/projekcje, batch RF vs baseline, Terraform entrypoint.
Nie nadpisuj danych ani implementacji. Oddziel uruchomione pomiary od static review.
Zaproponuj przypisany do etapów backlog i pierwszą małą zmianę z kryteriami odbioru.
```
