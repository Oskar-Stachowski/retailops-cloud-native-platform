# AI 09 — natywne plany z istniejącego zwykłego Source

`prepare_development_scenarios` otwiera jeden pełny zwykły Source 2.7 przez
oryginalny `read_source_dataset`. Ten odczyt sprawdza wszystkie tabele, hashe,
raporty i natywne zależności. Helper nie tworzy dodatkowego przebiegu kontrolnego.
Receptura przypina identyfikator Source, hash pełnej konfiguracji i trzy okna:
tune, calibration oraz development evaluation. Odrzuca final i wszystkie daty spoza już odsłoniętego development
2025-08-01–2026-07-31 przed odczytem.
Dopuszcza pełne development 25/50/100 z 365 dniami i dotychczasowe ograniczone
profile kontrolne. Wymaga seeda 42, 14 known forecast days i domyślnej konfiguracji
zapasu. Nie obcina danych ani historii źródła.

W każdym oknie powstają trzy rodzaje demand anomaly i dwa physical. Każda rola
demand ma odrębny produkt; wszystkie sześć interwencji physical ma odrębne
produkty, aby ich zapasy i zwroty nie naruszały poprzedzających clean controls.
Wybór wykorzystuje otwarte, aktywne ziarna natywnych obserwacji oraz istniejące
czynniki demand. Neutralne promocje i sezonowość pochodzą z innych produktów.
Cold start pozostaje osobną kontrolą. Kolejność wejściowych wierszy nie zmienia
wyboru. Zbyt mały lub niepoprawny zbiór kandydatów kończy się błędem.

Zwroty wybiera oryginalny `generate_return_events` uruchomiony na rzeczywiście
zrealizowanych zakupach zwykłego Source. Nie ma kopii losowań, polityk ani limitów
zakupionych jednostek. Kandydat musi dawać dodatnią liczbę dodatkowych zwrotów
w zadanym oknie. Stock cap wskazuje rzeczywisty dodatni demand outcome i jego
historyczną lokalizację realizacji. Są to dowody wykonalności planu, nie dowody
końcowych efektów: oba plany nadal muszą przejść cały natywny paired replay,
kontrole spillover oraz publikację i odczyt Source 2.8.

[Dowód](development-scenario-selection.json) zapisuje **21 zaliczonych kontroli**
bindings, odmów i stabilności kolejności. Pierwszy rzeczywisty mały Source
odczytano poprawnie, ale wybór zatrzymał `KeyError`: flagę otwarcia odczytywano
z truth zamiast obserwacji. Poprawiono właściciela pola oraz kontrolne fixtures.
Ten nieudany przebieg jest zachowany. Przegląd dodał także blokadę
ponownie zahashowanego ai-dev z przyszłymi datami i usunął warunek dodatniego
demand na dniu spike z wyboru niezależnych interwencji physical. Własny kontroler
odczekujący na RAM zatrzymano przed startem Source, aby sprawdzić poprawiony kod;
wynik 19 wcześniejszych kontroli i przyczyna zatrzymania pozostają zapisane.
Kontrola poprawionego wyboru i rzeczywistych
efektów nie wystartowała: po 30 minutach wygasło oczekiwanie na bezpieczny
budżet 512 MiB drzewa procesów i rezerwę 1 GiB RAM. Nie jest zaliczona
i nie uruchomiono automatycznej powtórki. Obydwa natywne testy są częścią
`pytest data/tests` zwykłego Required CI. Lokalnego pełnego `make ci-local`
nie uruchomiono przy obecnym obciążeniu hosta.

Zmiana pełnych scenariuszy będąca bazą tego helpera została scalona przez
[PR 113](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/113)
po 21 sukcesach i czterech deklarowanych pominięciach ścieżek Required CI;
walidacja wynikowego main `95aa6f0e` trwa osobno.

Helper nie jest samodzielnym uprawnieniem kampanii. Wykonawca AI musi przed
wejściem zarejestrować odczyt, jego koszt oraz wcześniejszy koszt przygotowania,
powiązać czysty producer/runtime i rzeczywiste role ewaluacji, a wynik zapisać
trwale przed próbami modeli. Należy też połączyć istniejący zwykły parent
z dziennikiem przygotowania i triali bez fikcyjnej ponownej generacji. Planowanie
final wymaga osobnej ścieżki po zamrożeniu wyboru; ten helper go odrzuca.
Pełne profile, krytyczne pokrycie, CI i publikacja na main pozostają otwarte.
AI 09 nadal jest `not_ready`.
