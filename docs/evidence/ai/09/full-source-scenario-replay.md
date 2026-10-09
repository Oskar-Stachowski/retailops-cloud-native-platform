# AI 09 — pełne profile w niezależnym odtworzeniu scenariuszy

Audyt natywnego Source ujawnił limit 5000 dziennych ziaren w dwóch samodzielnych
builderach kandydatów AI 07. Writer i reader Source 2.8 wykorzystywały te same
buildery do niezależnego potwierdzenia efektów. Poprawny plan większego profilu
nie mógł więc przejść publikacji, również po poprawnej generacji tabel.

Krótka kontrola przypiętego `ff2504a` odtworzyła blokadę demand i physical
dla pełnych profili 25/50: 45 625 i 91 250 ziaren. Nie generowała danych.
Samodzielne narzędzia AI 07 nadal zachowują limit 5000. Osobna ścieżka Source
dopuszcza ponadto tylko pełne konfiguracje AI 09: development 365 dni,
25/50/100 produktów, 5 par sprzedaży, 3 lokalizacje zapasu i seed42 oraz final
730 × 200 × 10 × 4 z seedami42/137/2026. Te konfiguracje wymagają 14 dni
known forecast plans. To dopuszczenie konfiguracji, nie uprawnienie do final.

Wspólne funkcje odtworzenia zachowują oryginalne generowanie obu przebiegów,
porównanie demand, kontrole efektów fizycznych i zwrotów, clean controls,
kontrolę latent demand, wszystkich ziaren spillover oraz niezależne porównanie
całych tabel Source i kontekstu. Nie filtrują historii, obserwacji ani słabszych
scenariuszy. Schematy i zasady publikacji Source 2.8 pozostają bez zmian.

Zmiana pamięci polega na wcześniejszym zwolnieniu pełnego przebiegu kontrolnego.
Zostają wszystkie redukcje wymagane do oryginalnych porównań, pełna mapa ilości
demand IDs i dzienne ilości dla całego spillover. `scenario_document` zwalnia
pełną strukturę kandydata przed niezależnym odtworzeniem tabel, ponieważ jego
dokument zawiera tylko plan i efekty. Wersja cached planned execution to 1.1.4;
przypięte hashe obejmują nowe granice profilu i funkcje odtworzenia.

Sześć natywnych porównań z funkcjami zaakceptowanego `ff2504a` potwierdziło
identyczny hash całej zawartości kandydata oraz efektów: demand/physical,
seedy42/137/2026, kontrolne 30 × 8 × 3 × 2 z 14 known days. Kontrola trwała
52,851 s i miała próbkowany szczyt RSS 175 734 784 B. Nowy stały test zawiera
wyłącznie te fingerprinty oraz przypięte konfiguracje i odwołanie do wersji
referencyjnej. To dowód zgodności małych kontroli, nie pełnej skali.

Regresja scenariuszy zaliczyła **85 testów**, bez pominięć (109,18 s).
[Dowód](full-source-scenario-replay.json) zawiera pomiary i hashe.
Pierwsza kontrola lokalna dała 16 passed / 2 failed;
dwie porażki wskazały brak `evaluated_at` w kontrolnym obiekcie testowym.
Fixture jest poprawiona. Następny przebieg przerwał monitor z powodu symlinków
tworzonych przez pytest w jego katalogu tymczasowym. Pliki tymczasowe testów
mają teraz osobny katalog; limity czasu/RAM i globalna rezerwa dysku pozostają.
Porażki i odmowy preflight są zachowane. Dodatkowy odbiór writer/reader,
qualification, eksportu i snapshotów oraz stałych fingerprintów zaliczył
**29 testów**, bez pominięć (569,96 s). Próbkowany szczyt RSS wyniósł
195 559 424 B; monitor zachował rezerwę RAM 1 GiB. Te kontrole obejmują
demand i physical dla seedów 42/137/2026 oraz pełne natywne tabele małych
profili kontrolnych. Pełny profil nie został jeszcze wygenerowany.

Przed akceptacją pozostają pełny lokalny preflight, Required CI oraz
publikacja na main.
Consumer AI musi następnie jawnie przypiąć zaakceptowany Source. Istniejący
pin kampanii i zamknięte artefakty AI 07–08 nie zostały zmienione. Nadal trzeba
przygotować rzeczywiste plany większych profili z poprawnymi natywnymi ziarnami
i przeprowadzić pełną kampanię AI 09. Ta poprawka nie jest dowodem `ready`.
