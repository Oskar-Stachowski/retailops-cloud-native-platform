# Kontrakt danych, czasu i tożsamości

**Status: wymagania do wdrożenia, nie opis gotowego systemu.** Wspólny kontrakt etapów 02–10. Decyzje tutaj zastępują sprzeczne zapisy pierwotnego raportu i specyfikacji. Zakres konkretnego etapu rozstrzyga, które bramki muszą już działać.

## 1. Właściciele i klasy danych

| Klasa | Właściciel i miejsce | Zasada dostępu |
|---|---|---|
| Obserwowalne fakty | RetailOps; `facts/` | Generator operacyjny, eksport przez jawny kontrakt |
| Prawda symulatora | RetailOps; `simulation_truth/`, w eksporcie `evaluation_truth/` | Wyłącznie generator i osobny proces ewaluacji |
| Raw events | RetailOps; `raw_events/` | Osobna ścieżka replay/DQ, nie automatyczny zamiennik poprawnych faktów |
| Curated, features, labels, splits | Repo AI; osobne manifesty i zbiory | Tylko zatwierdzone fakty; labels poza macierzą cech |
| Predykcje i rekomendacje | Repo AI; `predictions/` | Wyniki mają lineage; nie są domyślnie źródłowym targetem |

AI nie kopiuje generatora i nie czyta bazy RetailOps bezpośrednio. Legacy `forecasts.csv`, `anomalies.csv`, alerts i workflow actions mogą pozostać dla demo; eksportuje się je tylko jako `source_operational_output`, bez automatycznego dołączania do treningu. Nie są etykietami prawdy.

`latent_demand`, `lost_sales_units`, składniki szumu, prawdziwa elastyczność, mnożniki popytu i oznaczenia injekcji należą do truth. Dostęp do truth jest wyłączony w runtime API i w feature builderze. Osobne moduły, uprawnienia oraz jawna allowlista cech mają zapewniać tę granicę; samo usunięcie kilku kolumn nie wystarcza.

## 2. Grain i relacje

| Produkt danych | Grain / klucz | Minimalny kontrakt |
|---|---|---|
| Products | `product_id` | SKU bez whitespace, hierarchia, brand, launch/discontinue, jednostka |
| Assortment / channel assignment | produkt + selling location + channel + okres | Dozwolona kombinacja, daty obowiązywania, `available_at` |
| Fulfillment mapping | selling location + channel + okres | Dokładnie określona `stock_location_id` dla danego czasu i wersji |
| Price calendar | produkt + scope + okres + wersja | Cena/currency, zakres produktu/kanału/lokalizacji, known/available time |
| Promotions | promotion ID + scope + okres + wersja | Typ, rabat, known/available time, jawna reguła łączenia |
| Daily observations | `business_date + product_id + selling_location_id + channel` | Jawne zera, liczba sztuk/zamówień, przychody, returns, kompletność |
| Inventory ledger | `inventory_event_id` | Produkt, stock location, ruch, signed quantity, czasy, source reference |
| Replenishments | replenishment ID; receipts osobno | Dostawca, produkt, miejsce, zamówiona/przyjęta ilość, plan i realizacja |
| Forecast | produkt + selling location + channel + origin + target date | `target_type=observed_sales_units`, horizon, wersja modelu, lineage |
| Stockout risk | produkt + fizyczna stock location + origin + horizon | Wspólny zapas liczony jeden raz; mapowanie do kanałów tylko prezentacyjne |
| Anomaly observation | okno obserwacji + product/location/channel + detector version | Observed, expected, residual, score, reason codes, status danych |

`store_id` może być polem kompatybilności. Nie zastępuje pełnego grainu ani nie jest fikcyjnym identyfikatorem dopisywanym przez importer. Nie wybierać dowolnego magazynu przy brakującym mapowaniu.

Daily panel obejmuje wszystkie i tylko obowiązujące kombinacje produktu, miejsca sprzedaży i kanału. Zera są jawne, ale brak danych nie jest zerem. Utrzymać `is_active_assortment`, `location_open`, `source_data_complete`, `insufficient_history`. Zamknięty sklep w aktywnym asortymencie może mieć wiersz ze statusem closed i zerem; wiersz nie jest automatycznie dopuszczony do scoringu. Brakujące okno źródłowe ma unknown/missing i nie staje się obserwacją zerową. Wykluczone lifecycle/assignment combinations nie powiększają mianownika kompletności panelu. Raport podaje zarówno potencjalny iloczyn, jak i faktyczną liczbę ważnych kombinacji.

## 3. Czas i dostępność wiedzy

Wszystkie timestampy zapisuje się jako UTC z jawną strefą. Domyślne `business_timezone=UTC`, także dla wyznaczania `business_date` i granic origin. Wersjonowana konfiguracja może jawnie włączyć strefę IANA per lokalizacja, np. `Europe/Warsaw` lub `Europe/Berlin`; wymaga wtedy deterministycznej konwersji UTC, granic doby i testów DST oraz nowej identity. Nie mieszać stref w jednym grainie bez zapisanej polityki. Kalendarz obejmuje dni tygodnia, tygodnie/miesiące/kwartały, święta PL/DE według przypisanego kraju, Wielkanoc, Boże Narodzenie, Black Friday/Cyber Monday i skonfigurowane sezony kategorii; wersja kalendarza wchodzi do identity.

| Pole | Znaczenie |
|---|---|
| `occurred_at` / `sold_at` / `ordered_at` | Chwila zdarzenia biznesowego |
| `effective_from/to` | Okres biznesowego obowiązywania rekordu/planu |
| `ingested_at` | Chwila dotarcia do systemu |
| `available_at` | Najwcześniejsza chwila użycia danej wersji przez pipeline |
| `forecast_origin` / `as_of_time` | Granica wiedzy przy predykcji |
| `label_available_at` | Chwila, kiedy outcome jest dostatecznie zaobserwowany do ewaluacji/treningu |
| `watermark` | Zadeklarowana kompletność danego strumienia, nie maksimum dowolnej daty |
| `generated_at` | Metadane wykonania, nie dowód dostępności wiedzy historycznej |

Każda cecha ma `source_available_at <= as_of_time`. Przy kilku źródłach sprawdza się maksimum oraz lineage rekordów. Plan z przyszłym `effective_at` jest dopuszczalny, jeśli jego użyta wersja była znana w origin. Zrealizowana cena, stockout, sprzedaż, zwrot lub dostawa z przyszłego dnia nie są planem. Korekty są dopisywane jako wersje, nie nadpisują wiedzy historycznej. Dodanie późniejszej korekty nie może zmienić cech już odtworzonego origin.

Prognozę wystawia się przy jawnym cutoff na końcu doby biznesowej D; `target_date = D + h` dla `h=1..14`. Przy domyślnym UTC np. origin `2026-08-22T23:59:59Z`, horyzont 3 i target `2026-08-25` są spójne. Timestamp origin jest dokładną granicą wiedzy; rekord dostępny później, nawet w ostatniej części tej samej sekundy/doby, jest niedostępny. Precyzję timestampów/cutoff zapisuje się w kontrakcie. Nie mieszać tej konwencji z origin ustawionym na początek target day. Przy jawnej zmianie business timezone D oznacza datę w skonfigurowanej strefie, a zapis timestampu nadal jest UTC. Rolling one-step i fixed-origin 7/14 dni to oddzielne protokoły; późniejsze actuals można użyć w nowym rolling origin, lecz nie w zamrożonej prognozie.

Outcome forecastingu i stockout znajduje się po origin. Dla stockout label obejmuje `(t, t+7 dni]`, z osobnym `label_available_at`; niepełny tail jest censored, nie label 0. Stan zero już w origin ma `already_stockout`, poza zbiorem incydentalnego ryzyka. Anomaly detection ocenia już zaobserwowane okno: label dotyczy tego samego okna, ale nie trafia do cech, a expected value i robust scale pochodzą z wcześniejszych danych.

Predykcje upstream użyte w stockout lub anomaly features powstają przez rolling-origin/cross-fitting. Zapisuje się model, training/selection cutoff, preprocessing, źródłowe cechy i split. Dopuszczalne jest odtworzenie historycznego modelu dziś, o ile trening, preprocessing i dobór parametrów respektują historyczną granicę wiedzy. Model dopasowany do późniejszych outcomes nie uzupełnia wstecz cech downstream.

## 4. Handel i symulacja

Jedno źródło ceny i promocji zasila transakcje oraz obserwacje. Reguły scope i nakładających się promocji są wersjonowane, cena pieniężna ma ustaloną precyzję/zaokrąglenia i currency. Agregaty zrealizowanej ceny są outcome diagnostycznym, nie cechą znaną przed dniem prognozy.

Popyt latentny ma jedną jawną formułę: `base_rate × product_factor × location_factor × weekly_factor × seasonal_factor × lifecycle_factor × price_factor × promotion_factor × anomaly_factor × noise`. `demand_weight` działa dokładnie raz. Wszystkie składniki i zasady próbkowania/zaokrąglania są wersjonowane; latentny popyt pozostaje truth.

W etapie 02 pierwszy poprawny zbiór służy prognozie obserwowanej sprzedaży bez wiarygodnego ledgeru: inventory-dependent features są całkowicie wyłączone, a manifest deklaruje `inventory_ready=false`. Nie przedstawiać tego jako dowodu jakości stockout ani nieograniczonego popytu. Po etapie 06 obowiązuje `observed_sales = min(latent_demand, inventory_available)` dla wspólnej puli i chronologicznej alokacji. `lost_sales=max(0, latent-observed)` pozostaje truth. Zmiana procesu źródłowego wymaga nowych identity i ponownej ewaluacji forecastingu.

Koszyk nie zawiera powtórzonego SKU jako osobnych przypadkowych linii; dobór komplementarnych produktów jest bez replacement albo agreguje ilość według jawnej reguły. Zachować uzgodnienie order → items → sales. Wymagana chronologia to `ordered_at <= sold_at <= returned_at`, z opisanym wyjątkiem tylko dla rzeczywiście wprowadzonego procesu biznesowego. Nie zawijać godzin modulo. Zwrot dotyczy konkretnej pozycji, suma zwróconej ilości nie przekracza zakupu, a daty tailu i watermark są jawne. Returns wpływają na revenue oraz, jeśli kwalifikują się do ponownej sprzedaży, na ledger.

Ledger spełnia `closing=opening+sum(quantity_delta)` dla każdego product/stock location/dnia. Opening balance albo jednorazowy ruch otwarcia — nigdy obie wartości dodane ponownie. Cotygodniowy snapshot nie jest nowym opening movement. Dla równych timestampów ustalić deterministyczny sequence (np. jawny sequence number z generatora). Snapshot jest wynikiem ledgeru. Ten sam stock obsługujący kilka kanałów nie jest zwielokrotniony.

## 5. Manifesty i identity bez cyklu hashów

Każdy source, curated, feature set, label set, split i prediction dataset ma własny wersjonowany identity descriptor. Zawiera rolę, parent IDs, efektywną konfigurację, seed/scenariusze, wersje kontraktów, kalendarza i kanonizacji, źródłowy commit/transform code oraz lockfile hash i canonical content hashes. Zapisuje requested oraz resolved parameters, bez `null` zastępujących zastosowane domyślne liczby.

1. Ustalić kanonizację typów, decimal, null, UTC, nazw pól i sortowania wierszy po stabilnym kluczu. Hash logicznych danych jest niezależny od partycjonowania Parquet.
2. Descriptor nie zawiera własnego ID, runtime timestamps, lokalnych ścieżek ani hashów manifestu, który już zawiera ID. Własnego ID nie umieszczać w treści wyznaczającej to ID; parent ID jest dozwolony.
3. Wyliczyć `dataset_id=<rola>-sha256-<hash canonical descriptor>` i zapisać finalny manifest obok danych. Pełny manifest może dostać osobny checksum transportowy; nie definiuje nim własnej identity.
4. Każdy artefakt ma dodatkowo checksum SHA-256 bajtów, rozmiar, rows, grain, schema version, klasyfikację i faktyczny zakres dat. Oddzielić byte checksum od canonical content hash. Raporty mają wersję polityki, status i checksum; zmienne metadane wykonania nie zmieniają content identity.
5. Warianty release wymagają czystego commit state albo jawnego hash zmian kodu; samo SHA przy zmienionym lokalnym kodzie nie jest wystarczającym provenance.

Zmiana liczby produktów, seedów, konfiguracji, istotnej treści, kontraktu lub transformacji zmienia odpowiednią identity. Dwa identyczne przebiegi w tym samym kontrolowanym środowisku zachowują identity. Zmiana writer metadata może zmienić checksum bajtów bez zmiany logicznych danych, ale jest jawnie rozliczona. Testy obejmują source, curated, features, labels, splits oraz predictions.

Minimalny łańcuch: source dataset → curated → features/labels + split → training run → model version → inference run → predictions. Rejestracja w MLflow nie zastępuje manifestów.

## 6. Snapshot i migracja

Eksport i import weryfikują kompletny manifest, obsługiwane major versions, wszystkie checksums, klasyfikacje i gates właściwe dla use case’u. Zapis do katalogu tymczasowego; publikacja przez atomowy rename dopiero po weryfikacji. Ten sam ID z różną treścią jest konfliktem, nie nadpisaniem. Nie dopuszczać ścieżek artefaktów wychodzących poza root snapshotu.

CSV zachować dla demo i małych fixtures. Dane AI zapisywać w typed Parquet; duże fakty partycjonować po business date, z bounded/chunked writes. Repo śledzi demo i co najwyżej jeden mały fixture; duże eksporty i treningowe artefakty są ignorowane przez Git. Cleanup odmawia usunięcia śledzonego fixture.

Po etapach 06 i 07 reużyć eksport/import z etapu 03, wygenerować nowe manifesty i zaktualizować readiness; nie zmieniać opublikowanego snapshotu. Dawne modele zachowują lineage do swoich danych i nie uzyskują automatycznie zgodności z nowym feature schema.
