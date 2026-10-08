# AI 09: audyt pamięci i kosztu przygotowania danych

Audyt obejmuje generację Source, kwalifikację i eksport oraz niezależny import
i przygotowanie danych w repozytorium AI. Pełny profil, seedy, daty, 58 tabel,
oryginalny proces chronologiczny, RNG, reguły fizyczne i wszystkie bramki jakości
pozostają zachowane. AI 07–08 i wcześniejsze etapy pozostają zamknięte.

Szósta próba canonical, run `37765329151` w repozytorium AI, przekroczyła
limit 8 GiB RSS po 2967.75 s, przed ukończeniem generacji. Próbę i jej koszt
zachowano; kolejne uruchomienie wymaga zakończenia audytu i odbioru CI obu repo.
Stosy wskazują miejsca wykonywania kodu, lecz nie dowodzą właścicieli pamięci.

Wprowadzone poprawki:

- Świeżo wygenerowany prywatny kandydat zwalnia osiem nieużywanych starszych
  tabel przed symulacją; wszystkie 32 wejścia Source i prywatne tabele pozostają.
- Cached executor pożycza tylko odczytywane koszyki i stare obserwacje, które
  całkowicie zastępuje. Opublikowane mastery i plany nadal są niezależnymi kopiami.
- Zwroty, sumy zwróconych ilości, przyjęcia dostaw i pozycje koszyków mają indeksy.
  Sprawdzanie zwrotu względem zakupu, unikalności przyjęć, pełnej historii
  zamówienia, ilości skumulowanych i sald pozostaje obowiązkowe.
- Cache walidowanych ruchów przechowuje jeden obiekt zamiast pary. Rekordy
  zastępujące oryginalne ruchy są w pełni walidowane przy każdym widoku księgi.
- Po wykonaniu zwalniane są indeksy i typowane ruchy symulatora; przed niezależną
  rekonsyliacją zwalniana jest poprzednia typowana księga.
- Cache parsowania UTC oraz kwalifikacji mają limit 4096. Zamiana zapisu
  niezmiennych skalarów na zwykły słownik zachowuje zachowanie `asdict` dla
  niepoprawnych lub zastąpionych złożonych wartości.
- Hash JSON tabel i kanoniczne pliki kwalifikacji są przetwarzane strumieniowo.
  Porównanie pliku sprawdza każdy bajt, kolejność, typy i jedyny końcowy newline.
  Większe multisety CSV sortuje SQLite z ograniczonym cache. Jego pliki
  tymczasowe respektują mierzone `TMPDIR` runnera.
- Odczyt Source sprawdza normalizację wiersz po wierszu i kompiluje reguły CSV
  raz dla tabeli, bez budowania drugiej kopii całego zestawu.
- Zapis Source może przyjąć jawne `consume_input=True` wyłącznie dla prywatnego,
  świeżego stanu runnera. Domyślny wywołujący zachowuje wejścia. Writer zwalnia
  znormalizowane tabele przed pełnym niezależnym odczytem staging; publikacja
  nadal jest atomowa i poprzedzona wszystkimi bramkami.
- Eksport i jego verifier konwertują i haszują porcje do 8192 wierszy. Pełna
  kopia skonwertowanej tabeli znika; wszystkie schematy, content/ranges, ziarno,
  rekonsyliacja i niezależny replay planów pozostają wymagane.

Source 2.7/2.8 i snapshot 1.1/1.2 zachowują swoje kontrakty. Nowe wersje
implementacji to `inventory-source-cached-ledger-2.2.0` oraz
`planned-source-cached-execution-1.1.0`. Przypięcia upstream są aktualizowane
jawnie; stare zamrożone commity i receptury pozostają niezmienne.

323 kontrole wszystkich zmienionych obszarów przeszły przed końcowymi poprawkami
retencji; kolejne 64 potwierdziły uproszczenie cache ruchów. Ostateczny odbiór
tych samych natywnych tabel/CSV, scenariuszy demand/physical na trzech już
odsłoniętych seedach, kontraktów i całego Required CI jest wymagany dla końcowego
head. Końcowy kod z uproszczonym cache i zwalnianiem ośmiu tabel zaliczył
64 kontrole w 423.42 s; Mypy 43 plików, Ruff i format 158 plików są poprawne.
Nie kwalifikuje to modeli ani pełnego profilu canonical.

Jedna mała para przeszła 5/5 faz w obu implementacjach: 58 tabel Source oraz
43 tabele eksportu, importu i curated mają identyczną treść logiczną, zakresy
i liczbę odrzuceń. Trzy świeże pary pełnego małego build, przed ostatnią redukcją
retencji, dały medianę CPU −13.11%, RSS procesu −4.92% i peak alokacji Python
−2.11%; retained Python wzrósł o 0.80%. To pomiary małych kontroli, a ich wall
time może zależeć od równoległych lokalnych testów. Pełny RSS, scratch i czas
canonical nadal wymagają oddzielnego pomiaru. Nie zmieniono limitów ani profilu.

Końcowe trzy świeże pary dały medianę CPU −16.78% i peak alokacji Python
−5.18%, przy retained Python +0.69% oraz RSS procesu +2.51%. Pojedyncza końcowa
para pięciu faz nadal zachowała wszystkie treści i zakresy; CPU curation wzrósł
o około 4.85%. Zysku pełnego RSS nie potwierdzamy. Zachowujemy także wcześniejsze
pomiary i koszty, zamiast wybierać wyłącznie korzystne wyniki.

Nie wykonano nowych projektowych fitów ani odczytów świeżego final testu.
Poprawki i testy są wykonywane w osobnych worktree; otwarte sesje i usługi
użytkownika pozostają nienaruszone.
