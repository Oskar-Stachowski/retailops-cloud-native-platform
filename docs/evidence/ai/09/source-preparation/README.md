# AI 09 — ograniczenie kopii i dziennego replayu producenta

Pełny diagnostyczny `ai-dev` producenta `1de4627` przekroczył limit 4 GiB
podczas generacji. Osobna próba z limitem 8 GiB używa tego samego producenta;
te zmiany nie modyfikują jej danych ani kodu. Wynik i koszt każdej próby są
zachowane w repo AI.

`source_bridge` kopiuje teraz tylko tabele konsumowane lub zwracane przez
symulator commerce oraz potrzebne prywatne parametry cen i produktów.
Każdy taki rekord nadal ma odłączoną kopię. Pełny pierwotny candidate pozostaje
dostępny dla source foundation i reconciliation. Nie usunięto danych z gotowego
źródła ani nie dodano truth do wejść modelu.

Dzienne snapshoty stosują każdy ruch ledgeru raz, jeżeli zbiory widocznych
ruchów na kolejnych dziennych cutoffach są chronologicznymi prefiksami.
Spóźniona dostępność zmieniająca tę kolejność uruchamia dotychczasowy pełny
replay. Zachowano całą walidację bilansu, kolejność wierszy, statusy unknown,
cutoffy, częściowe dni, counts, dostępność i identyfikatory snapshotów.
Publiczne `snapshot_at`, schematy i wcześniejsze limity pozostają zgodne.

## Wykonany odbiór

Nowe testy porównują kompletny native commerce z dawnym `deepcopy(candidate)`
na seedach 42, 137 i 2026, z planami forecast oraz z rzeczywistym planem anomalii
fizycznych. Testy snapshotów porównują wszystkie pola i komunikaty błędów z
dawnym replayem: zwykła historia, późne fakty, brak pozycji, dzień przed opening,
częściowy dzień oraz zmiana dostępności w obrębie jednego dnia.

Łączna regresja 16 plików przeszła: **456 passed w 122.85 s**, bez wyłączeń.
Obejmuje źródła inventory/forecast/anomaly, fizyczne anomalie, stockout stress,
profile supply/delivery/fault, ledger, projection, snapshot i qualification.
Ruff broad ALL oraz format dwóch zmienionych modułów są zaliczone.
Konfiguracja Mypy producenta nadal obejmuje pięć istniejących modułów backendu;
nie jest odbiorem typów całego generatora.

Pierwsza regresja istniejących ścieżek AI 08 celowo zatrzymała się na strażniku
zmienionego pliku commerce: 1 failed i 15 errors, przed użyciem fast path.
Po przeglądzie wcześniejszych porównań z kompletną kopią zaktualizowano dokładne
przypięcia `source_bridge.py` i wynikowego `source_cohort_batch.py`.
Strażniki nie zostały wyłączone. Osobny odbiór ma **16 passed w 12.73 s**:
kompletne 58 tabel, identyczne CSV i kontekst, ordinary writer/reader i 36 bramek,
każdy review, pending transfer, duplicate IDs, ujemne bilanse, zastąpione błędne
rekordy i zmieniony master. Indeks identyfikatorów oraz cached ledger pochodzą
z istniejącej pracy AI 08; kolejny pomiar może wykorzystać tę odebraną ścieżkę.

Dodatkowe **3 passed w 24.02 s** porównują ordinary i cached źródło z 14 dniami
znanych planów forecast, na seedach 42, 137 i 2026. Każdy przypadek zachowuje
całe 58 tabel, identyczne CSV/source ID i kontekst, zwykły writer/reader oraz
zaliczone bramki source. To kontrolne `ai-load` 45 × 2 × 1 × 1, bez model fits
lub final testu.

Required CI początkowego HEAD wskazał także jedną podatność high w przechodniej
zależności frontendu `source-map-js`. Lock zmienia wyłącznie jej wersję
1.2.1 → 1.2.2, URL i integrity. [Advisory](https://github.com/advisories/GHSA-68fv-2mgg-jv7q)
wskazuje 1.2.2 jako wersję z poprawką. Po `npm ci` audyt wszystkich zależności
ma 0 podatności; lint, 36 testów Node oraz produkcyjny build przechodzą.
Nie zmieniono reguł security CI.

[Pomiar](components.json) obejmuje pięć par na native `ai-load`:
90 dni, 8 produktów, 2 pary sprzedaży, 2 stock locations, seed 42 i 14 dni
znanych planów. Powstały 3834 ruchy ledgeru oraz 1440 snapshotów. Kolejność
old/new zmieniała się między parami; kompletne wyniki snapshotów są zgodne.

| Komponent | Mediana poprzednio | Mediana po zmianie | Zmiana |
| --- | --- | --- | --- |
| Alokacje Python podczas kopii wejść | 16709064 B | 14234096 B | −14.81% |
| CPU dziennych snapshotów | 0.153275 s | 0.015907 s | −89.62% |
| Wall dziennych snapshotów | 0.160791 s | 0.016883 s | −89.50% |

Alokacje mierzono przez `tracemalloc` tylko wokół kopii. CPU i wall projekcji
mierzono oddzielnie, bez tracemalloc; porównanie używa tej samej instancji
native ledgeru i tej samej konfiguracji cutoffów. Hash obejmuje kompletne
kanoniczne bajty wyników. `components.json` zawiera każdą parę, konfigurację,
platformę i hashe zmienionych modułów.

Dwie pierwsze próby przygotowania pomiaru miały błędy w pomocniczym driverze:
brak wymaganego `max_daily_rows`, potem zły poziom pola `scenario.settings`.
Ich logi są zachowane; nie wykonywały fitów ani końcowej oceny projektu.

To pomiar komponentów na kontrolnym profilu. Nie zmierzono RSS całego drzewa
ani przyspieszenia całego pipeline. Pełne `ai-dev` i `ai-training` wymagają
nowego pomiaru na opublikowanym producencie, z zachowaniem wcześniejszych prób.
AI 09 pozostaje `in_progress`; nowa kampania, projektowe fity i final test
nie zostały rozpoczęte. AI 07–08 są zamknięte i nie wymagają ponownego odbioru.
