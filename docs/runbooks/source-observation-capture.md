# Capture obserwacji Source i replay korekt

Status AI 10: `in_progress`. Ten protokół obejmuje wyłącznie niezmienne
`daily_demand_versions` emitowane przez opt-in Source observation outbox.
Nie zastępuje pełnego, 43-table SourceSnapshot 1.2. Legacy sales oraz generator
nie emitują tych zdarzeń automatycznie.

## Procedura

1. Wykonaj istniejącą migrację `a10f0c7e0500` i migracje późniejsze na własnej
   bazie Source. Zachowaj oryginalne facts, event bytes i wersje historii.
2. Przygotuj poza Git pliki konfiguracji bazy i brokera `0600`, zgodne z CLI
   `services/api/scripts/source_observations.py`. Konfiguracja brokera zawiera
   prawdziwy cluster/topic ID, topic `retailops.source-observations.v1`, TLS CA
   i osobnego użytkownika SCRAM z prawem READ. Nadaj mu uprawnienia do topicu
   oraz grup z prefixem `ai10-observation-`. Capture nie wymaga WRITE ani
   zapisu consumer offsets.
3. W osobnym publisherze opróżnij pending outbox. Potwierdzenie ACK poprzedza
   SQL delivery receipt. Crash w tej granicy wymaga ponownej publikacji tych
   samych bytes i ID; wcześniejszy broker record musi pozostać w capture.
4. Wybierz nowy plik docelowy w prywatnym katalogu. Istniejącego pliku CLI
   nie nadpisuje. Uruchom z `services/api`:

   ```sh
   PYTHONPATH=. python scripts/source_observations.py capture \
     --database-config /private/source/database.json \
     --broker-config /private/source/reader.json \
     --output /private/source/capture.json
   ```

5. Capture utrzymuje krótko blokadę SQL authority, wspólną z append/publish,
   w transakcji REPEATABLE READ. Odczytuje pełny census SQL oraz wszystkie
   broker offsets `0..H-1` na każdej partycji. Porównuje bytes, hashes, event
   ID, key, wersje historii i ostatni delivery receipt. Powtórzenia przed
   receipt nie znikają z prefixu. Odczyt nie zapisuje ACK/cursor w brokerze.
6. Przed seal capture ponownie sprawdza rzeczywisty topic ID i pełny wektor
   watermarks, nadal pod tą samą blokadą. Pending outbox, retention z low
   watermark większym od zera, obcy record, luka, zmieniony topic/vector lub
   niekompletna historia przerywają operację. Limit to 32 partycje, 10000
   wersji, 20000 receipts i 16 MiB; broker prefix ma termin odczytu 20 sekund.
   Po usunięciu przyczyny ponów operację do nowego pliku. Nie zmieniaj faktów
   ani nie pomijaj partycji, aby dopasować je do limitu.
7. Po powodzeniu plik powstaje atomowo jako `0600`. Publiczny raport zawiera
   capture ID, counts i kompletny wektor. Przekaż oryginalne bytes oraz
   zaufany stream/partition count odbiorcy AI; nie wyznaczaj granic jedynie
   z SQL delivery offsets publishera.
8. Odbiorca AI waliduje przypięty kontrakt `source-observation-capture-1.0`
   oraz semantyczne wiązania całego prefixu. `ObservationHistory.restore`
   wymaga oczekiwanego streamu i wszystkich partycji. Replay może zacząć się
   wcześniej niż H: overlap deduplikuje się bez doliczania ilości.
9. Nowa korekta po H tworzy następną wersję. Quantity as-of wybiera ostatnią
   dostępną wersję ziarna, zamiast sumować wersje. Capture pozostaje niezmienny;
   kolejny pełny replay i capture + overlap muszą dać identyczny końcowy seal.
10. Zachowaj oddzielnie dowody wykonania i scope. API CI wymaga realnego SQL
    oraz TLS/SCRAM brokera i publikuje `source-observation-capture-evidence`:
    receipt, oryginalny capture, replay i JUnit. Test przerywa publisher po
    realnym ACK, odzyskuje retry, seal 2 facts / 3 receipts, a następnie
    publikuje trzecią wersję. Są to jawnie generowane obserwacje do odbioru
    protokołu. Dowód nie kwalifikuje modeli, nie tworzy pełnego 43-table
    handoffu i nie oznacza gotowości całego AI 10.

Kontrakt jest skopiowany bez zmian z dokładnego commitu AI wskazanego przez
`services/api/app/contracts/source-observations-v1/capture-upstream.json`.
Pełne requirements etapu pozostają w
[planie AI 10](../plans/ai/etapy/10-integracja-retailops.md).

## Niezależny odbiór SQL i ACK po stronie AI

Dedykowany workflow AI10 może ustawić równocześnie
`AI10_SOURCE_CAPTURE_RECEIVER_PYTHON` oraz
`AI10_SOURCE_CAPTURE_RECEIVER_SCRIPT`. Source utrzymuje oryginalny broker
i własną bazę do końca tego odbioru; poświadczenia readera przekazuje tylko
w tymczasowym pliku `0600`, poza uploadem.

1. Zamknięty runtime AI porównuje Source commit, oryginalny capture, replay
   i prawdziwe cluster/topic IDs. Własny jednorazowy PostgreSQL jest osobną
   bazą AI; odbiorca nie zapisuje projekcji w SQL Source.
2. Istniejący `ObservationRunner` odczytuje oryginalne trzy rekordy przez
   TLS/SCRAM, zapisuje facts/receipts/checkpoints atomowo w AI i potwierdza
   odczytane offsety. SQL capture AI musi być identyczny z capture Source.
3. Kontrolowane cofnięcie wyłącznie własnej grupy odbiorcy odtwarza trzy
   stare rekordy i późną korektę. SQL zachowuje trzy wersje i cztery receipts,
   a ilość zmienia się z 4 na 7; żaden duplikat nie dolicza wkładu.
4. Druga własna grupa wykonuje cały prefix od zera. Pełny SQL replay,
   capture + overlap oraz niezależny receiver in-memory mają identyczny seal.
   Raport zawiera rzeczywisty prefix/final ACK wszystkich trzech partycji.
5. Odbiorca usuwa wyłącznie własny kontener AI po sprawdzeniu UUID label.
   Source usuwa prywatny control po powrocie procesu. Publiczny
   `independent-ai-sql-handoff.json` zawiera tylko bindings, counts i offsety.

Ten opt-in ma zaliczony rzeczywisty
[CI run 37607732767](https://github.com/Oskar-Stachowski/retailops-ai-intelligence/actions/runs/37607732767):
Source `f4535a3`, AI `0d75f59`, 9 testów bez pominięć, sumy 4 → 7 i
rzeczywisty final ACK `[0, 0, 4]`. Niezależnie sprawdzono ZIP SHA
`a145565bf85a8bc2fc27eaa3492473b856f01471f067cd0ae189e7e05a5a5401`;
receipt jest zachowany w AI `docs/evidence/ai10-source-sql-handoff-accepted.json`.
Nie rozszerza zakresu na pełny 43-table SQL snapshot ani nie
kwalifikuje modeli. Zwykły capture pozostaje odczytem bez zapisu offsetów;
ACK w tej ścieżce należy wyłącznie do osobnej grupy odbiorcy AI.
