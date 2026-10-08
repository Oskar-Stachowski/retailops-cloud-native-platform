# AI09 — ograniczenie kopii w cached source

Pełny pomiar development w AI09, run `37676033214`, zakończył generację po
1751.743 s z `tree_rss_limit`, ponad 8 GiB. Już korzystał z indeksu ID,
cached walidacji ledgeru i zwalniania build state wprowadzonych w AI08.
Etapy AI07/08 pozostają zamknięte. Ten wynik nie jest kwalifikacją pełnego
profilu ani próbą modelu; poprzednie porażki i ich koszty pozostają zachowane.

Zwykłe source orchestration ma już helper `_copy_commerce_inputs`, który kopiuje
wyłącznie potrzebne tabele oraz trzy prywatne wejścia symulatora. Cached
`source_cohort_batch_v2` nadal kopiował cały kandydat. Teraz korzysta z tego
samego przypiętego helpera. Każdy konsumowany rekord nadal jest odłączony od
rodzica; source process, RNG, quality gates i publikowane kontrakty nie zmieniają
się. Upstream pins nadal są sprawdzane przed użyciem.

[Receipt kontroli](ai09-cached-cohort-copy-scope.json) zawiera 23 zaliczone testy:
parity wszystkich 58 tabel, CSV, source context, walidację writer/reader,
trzy seedy z 14 dniami planów forecast, niezależność rodziców po mutacji wyniku
oraz pominięcie niekonsumowanych wejść. Pierwsze cztery nowe fixtures nie miały
wymaganego limitu `max_daily_rows`; wpisano jawne 90, zachowując guard produkcji.

Kontrola alokacji Pythona na `ai-load` 45 × 2 × 1 × 1, seed42, pokazuje
916576 B peak pełnej kopii i 807816 B kopii konsumowanych tabel: mniej o 11.87%.
To pomiar komponentu przez tracemalloc, nie RSS procesu, CPU całego generatora
ani koszt ukończonego canonical profilu. Nie wolno stosować tej proporcji do
8 GiB całego świata. Pełny pomiar wymaga osobnej zamrożonej receptury po
Required CI i protected publikacji; zachowuje wszystkie trzy porażki,
canonical rozmiary, budżety i rezerwy. Nie jest uruchamiany automatycznie.
