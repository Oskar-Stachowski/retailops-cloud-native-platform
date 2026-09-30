# OPS-06 — przypięte wejścia builda i workflow

Pomiar: **2026-09-30**, kod `4ab97e6632e2b78a3b98c7c7a51cfd21dca7df3a`,
Darwin ARM64. Dokładne SHA, digesty indeksów, materials BuildKit, sumy plików
źródłowych i tożsamości wynikowych obrazów:
[local-verification.json](local-verification.json).

## Zakres

Bezpośrednie zewnętrzne Actions w workflow i lokalnych composite actions
mają pełne SHA z repozytoriów dostawców oraz komentarze z wersjami.
Bazy API/frontendu i zewnętrzne obrazy Compose, Kubernetes, testów awarii
oraz narzędzi CI mają digesty. Indeksy wieloplatformowe zachowują ARM64/AMD64.
Nie zmieniono linii Python 3.11, Node 22 ani schematu danych.

Required CI wykonuje [kontrolę referencji](../../../../scripts/ci/check_immutable_inputs.py)
bez dodatkowych zależności Python. Inwentaryzacja przechodzi: **171 referencji**,
w tym **16 unikalnych SHA Actions i 16 digestów obrazów**. Kontrola rozróżnia
zewnętrzne obrazy od jawnych lokalnych nazw aplikacji i aliasów etapów Dockerfile.
Nie dopuszcza tagów ani skróconych SHA jako zewnętrznych pinów.

Builder zapisuje rzeczywiste materials, platformę, sumy Dockerfile i plików
zależności oraz wynikowy digest. Manifest rejestru v3 zachowuje receipt i
sumę osobnego pliku metadanych każdego obrazu. W podpisanym pakiecie są też
tożsamości Actions i sumy plików harnessu. Publikacja odrzuca brakujące lub
podmienione receipts i bazę kandydata bez digestu. Import sprawdza powiązanie
wejść z kodem eksportowanym z Git.

Dependabot aktualizuje Actions, Dockerfile i wszystkie utrzymywane Compose
przez PR. Ręczne aktualizacje obrazów narzędzi mają tę samą procedurę
i bramki; opisuje je [runbook](../../../runbooks/build-input-updates.md).

## Wyniki wykonania

- **20 testów** granic wydania, receipt i odmowy publikacji.
- **11 testów** odmowy ruchomych referencji, skróconych SHA i dynamicznych narzędzi.
- **16 testów** macierzy wyboru Required CI.
- Ruff check/format, YAML, przypięty actionlint, Compose i wszystkie profile:
  zaliczone; `git diff --check` bez błędów.
- Rzeczywisty build poprzednika `75f59c9` i kandydata `4ab97e6`, upgrade,
  wymuszona awaria API i rollback: **passed**, **113,974 s**, cleanup **passed**.
  HTTP, przeglądarka, dane i idempotencja przechodzą w każdym z trzech stanów.
  Zmieniona historia migracji i nieznana rewizja DB są blokowane przed rollbackiem.

Pierwsza próba zatrzymała się na braku lokalnego Chromium. Po pobraniu wersji
wskazanej przez zainstalowany Playwright przez zweryfikowane TLS oficjalnego
CDN powtórzono cały drill na tym samym, czystym commicie. Za wynik odbioru
uznano wyłącznie tę pełną próbę. Surowe wyniki pozostają w ignorowanym
katalogu raportów lub tymczasowym; JSON powyżej zachowuje oczyszczony receipt.

## Granice

To odbiór wejść obecnej platformy i lokalnego wydania, bez nowej publikacji
GHCR, tagu lub wdrożenia AWS. Dawny poprzednik zachowuje deklaracje tagów,
ale raport rejestruje faktycznie użyte digesty. Istniejące podpisane dowody
historycznych wydań nie zostały zmienione.

Nie jest to obietnica bajtowo identycznego builda ani całego grafu zasobów
pobieranych przez dostawców Actions. Zewnętrzne repozytoria pakietów i dane
skanerów mają własną zmienność. Wydanie i rollback wybierają zachowane,
zweryfikowane artefakty. Wynik zdalny dla konkretnego SHA należy sprawdzić w
[Required CI](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/actions/workflows/required-ci.yml).
