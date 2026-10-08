# AI09 — zwalnianie przetworzonych zdarzeń symulatora

Ostatni pełny pomiar development, AI run `37731200719`, przekroczył 8 GiB RSS
po 1836.06 s w generacji. Nie ukończył żadnej z pięciu faz. Wszystkie pięć
dotychczasowych porażek i ich koszty pozostają zachowane; pełny profil nadal
nie ma kwalifikacji zasobów.

AI08 już wprowadziło indeks ID, cache walidacji ledgeru i zwalnianie build
state. Przyrost Source #105 wykorzystuje istniejącą kopię konsumowanych wejść.
Nowa zmiana w cached simulator zwalnia dodatkowe referencje do typowanych
list scenariusza dopiero po pełnej walidacji i włożeniu wszystkich zdarzeń
do oryginalnej kolejki. Kolejka nadal przechowuje każde zdarzenie do jego
wykonania. Metadane runtime są ponownie walidowane; pełny scenariusz rodzica
pozostaje w wejściach i effective configuration. Oryginalny simulator,
reguły fizyczne, RNG, schematy, gate'y i profile pozostają przypięte.

[Receipt](ai09-queue-event-memory.json) zawiera 33 zaliczone testy: wszystkie
58 tabel i CSV, context, pełny writer/reader, ledger po każdym review, plany
forecast, trzy kontrolne seedy oraz brak mutacji rodziców. Nowa kontrola
porównuje całą kolejkę przed wykonaniem i pełny wynik po wykonaniu. Weakrefs
potwierdzają zwalnianie obiektów podczas review, a nie tylko po usunięciu
symulatora. Błędne referencje, podwójne timestamp/sequence i zdarzenia poza
oknem są odrzucane przed zwolnieniem list.

Trzy pary osobnych procesów korzystają z już eksponowanego fixture parity:
10 dni, 8 produktów, 2 sklepy, 2 magazyny, seed `710001`. Bazowa kontrola
wyłącza wyłącznie nowe zwalnianie list. Wszystkie sześć wyników i wejść ma
identyczne digesty. Po wykonaniu bazowy symulator zatrzymuje 416 typowanych
zdarzeń; nowy zatrzymuje zero, zachowując wszystkie 416 rekordów wejścia.
Mediana peak alokacji Python spadła z 2889975 B do 2442115 B, o 15.50%.
Mediana zachowanych alokacji spadła z 2700251 B do 2252311 B, o 16.59%.

To pomiar konstruktora i wykonania małego komponentu przez tracemalloc.
RSS obejmuje całe życie procesu, a czasy obejmują tracemalloc i GC; wyniki
czasowe nie dowodzą przyspieszenia. Nie przenosimy tych proporcji na całe
8 GiB generatora. Required CI dokładnego headu, protected publikacja,
CI wynikowego main i osobny pełny pomiar na zaakceptowanym producencie
pozostają wymagane. Nie uruchomiono kampanii projektu, fitów ani świeżego
final testu. AI07/08 pozostają zamknięte, a AI09 nadal jest `not_ready`.
