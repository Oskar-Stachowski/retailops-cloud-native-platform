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
produkty. Trzy siedmiodniowe kontrole porównawcze demand znajdują się przed
pierwszą interwencją całego planu. Zmiana popytu jednego SKU zmienia wspólne
koszyki, identyfikatory sprzedaży i późniejsze zwroty innych SKU; sam wybór
innego produktu nie gwarantuje niezmienionego zapasu w późniejszym oknie.
Liczba i długość kontroli oraz wszystkie dziewięć epizodów demand pozostają
zachowane. Te okna porównawcze nie dowodzą pokrycia clean w późniejszych rolach
ewaluacji: trzeba osobno ocenić pełny zwykły Source i wymagane grupy, bez
automatycznego uznania niezbadanych ziaren za clean. Physical zachowuje sześć
kontroli poprzedzających własne interwencje.
Wybór wykorzystuje otwarte, aktywne ziarna natywnych obserwacji oraz istniejące
czynniki demand. Neutralne promocje i sezonowość pochodzą z innych produktów.
Cold start pozostaje osobną kontrolą. Kolejność wejściowych wierszy nie zmienia
wyboru. Zbyt mały lub niepoprawny zbiór kandydatów kończy się błędem.

Zwroty wybiera oryginalny `generate_return_events` uruchomiony na rzeczywiście
zrealizowanych zakupach zwykłego Source. Oryginalny `simulation_entities`
dołącza oddzielone parametry produktów, tak jak w natywnym symulatorze;
opublikowane fakty oraz tabele zakupów pozostają niezmienione.
Nie ma kopii losowań, polityk ani limitów
zakupionych jednostek. Kandydat musi dawać dodatnią liczbę dodatkowych zwrotów
w zadanym oknie. Stock cap wskazuje rzeczywisty dodatni demand outcome i jego
historyczną lokalizację realizacji. Są to dowody wykonalności planu, nie dowody
końcowych efektów: oba plany nadal muszą przejść cały natywny paired replay,
kontrole spillover oraz publikację i odczyt Source 2.8.

[Dowód](development-scenario-selection.json) zachowuje wcześniejsze **21 kontroli**
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
i nie uruchomiono automatycznej powtórki.

Pierwszy Required CI PR 114 zakończył się wynikiem **1156 passed / 2 errors**
w zestawie danych. Fixture 128×8×2×2 miała wyłącznie sklepy zamknięte w niedziele
i święta: w każdej roli było zero kandydatów otwartych przez wymagane okno.
Mała kontrola używa teraz trzech par sprzedaży, obejmując kanał online obecny
także w pełnym profilu pięciu par. Zachowuje natywny kalendarz, długości epizodów,
wszystkie produkty i pełne 128 dni; nie skraca okien ani nie wypełnia braków.
Osobny test potwierdza odmowę dla cotygodniowych zamknięć.

Kolejny natywny przebieg odtworzył `KeyError: return_rate`: parametry symulacji
nie są polami publicznej tabeli produktów. Poprawiono odtworzenie parametrów
przez ich oryginalnego właściciela. Następny przebieg zaliczył pełny zapis
i niezależny odczyt Source 2.8 physical, lecz odrzucił demand z powodu
spillover do dwóch późniejszych clean controls. Odrębna diagnoza zachowała
ten błąd bez pomijania natywnych kontroli. Przeniesienie porównawczych okien
demand przed wszystkie interwencje usuwa błędne założenie niezależności SKU.
Ostateczny wynik obu rodzin, koszty i nieudane kontrole zapisuje dowód JSON.
Końcowa kontrola poprawionego kodu uzyskała **23/23** testów kontrolnych
i **2/2** natywnych, bez pominięć. Pełny przebieg natywny trwał 442,54 s;
próbkowany szczyt drzewa wyniósł 373 374 976 B, minimalna dostępna pamięć
1 232 142 336 B. Zachowano limit 512 MiB oraz rezerwę 1 GiB RAM i 6 GiB dysku.

Obydwa natywne testy są częścią `pytest data/tests` zwykłego Required CI.
Obejmują teraz oryginalny writer i reader Source 2.8, pełne 58 tabel,
powiązanie planu oraz wszystkie rzeczywiste efekty i clean controls.
Nie oznaczają odbioru pełnych profili 25/50/100. Pierwszy CI miał również
niezależny błąd Docker Hub 429 podczas pobierania niezmienionego obrazu bazowego.
Zachowano logi obu przyczyn; nie ponowiono starego head bez korekty kodu.
Lokalnego pełnego `make ci-local` Source nie uruchomiono przy obecnym obciążeniu hosta.

Zmiana pełnych scenariuszy będąca bazą tego helpera została scalona przez
[PR 113](https://github.com/Oskar-Stachowski/retailops-cloud-native-platform/pull/113)
po 21 sukcesach i czterech deklarowanych pominięciach ścieżek Required CI;
wynikowy main `95aa6f0e` również uzyskał 21 sukcesów i cztery deklarowane pominięcia.

Helper nie jest samodzielnym uprawnieniem kampanii. Wykonawca AI musi przed
wejściem zarejestrować odczyt, jego koszt oraz wcześniejszy koszt przygotowania,
powiązać czysty producer/runtime i rzeczywiste role ewaluacji, a wynik zapisać
trwale przed próbami modeli. Należy też połączyć istniejący zwykły parent
z dziennikiem przygotowania i triali bez fikcyjnej ponownej generacji. Planowanie
final wymaga osobnej ścieżki po zamrożeniu wyboru; ten helper go odrzuca.
Pełne profile, krytyczne pokrycie, CI i publikacja na main pozostają otwarte.
AI 09 nadal jest `not_ready`.
