# AI 09: rzeczywisty postęp przygotowania Source

Generator może raportować postęp w kontekście
`data.generator.progress.reporting(stream, interval_seconds=60)`.
Każdy rekord `RETAILOPS_PROGRESS` ma wersję `source-progress-1.0.0`,
kolejny numer, czas UTC, czas od rozpoczęcia i nazwę wykonywanej operacji.
Zapis kończy się natychmiastowym `flush()`.

Markery obejmują budowę kandydatów i planned Source, symulację chronologiczną,
projekcję inventory, uzgodnienia, normalizację, każdą natywną kontrolę raportu,
kwalifikację etykiet oraz zapis i odczyt Source. Liczniki podają faktycznie
przetworzone rekordy i zdarzenia. Całkowita liczba zdarzeń jest nieznana do
opróżnienia kolejki, ponieważ symulacja dopisuje przyszłe zdarzenia.
Liczba zakończonych dni wynika z rzeczywistej daty aktualnego zdarzenia;
po opróżnieniu kolejki obejmuje całe okno symulacji. Odczyt i zapis tabel
podają rzeczywistą liczbę wierszy oraz oczekiwaną liczbę z inwentarza.

Kontekst niczego nie pobiera z wyprzedzeniem, nie zmienia kolejności zdarzeń,
RNG, ledgeru, popytu, zwrotów ani danych. Bez aktywnego kontekstu dekoratory
wywołują dotychczasową funkcję. Dane operacyjne mają własne fingerprints
kodu; nowy commit wymaga ponownego przypięcia producenta przez konsumenta.
Kontrakty danych i wersje algorytmów cached pozostają zachowane.

Nie wyliczamy procentu ukończenia ani ETA. Przerwy w wywołaniach natywnych
mogą opóźnić licznik Source; oddzielny supervisor AI ma wtedy emitować heartbeat
z RAM i CPU, wyraźnie odróżniony od postępu pracy. Sam ten komponent nie
potwierdza widoczności logów w działającym GitHub Actions UI. Taka kontrola
oraz chroniony odbiór dokładnego head i wynikowego main są jeszcze wymagane
przed nową długą diagnostyką.

Awaria raportowania podczas obsługi błędu zachowuje pierwotny wyjątek i dodaje
krótką informację o niedostępnym zdarzeniu błędu. Treść wyjątków, rekordów
danych i zmienne lokalne nie są emitowane. Błąd zapisu markera sukcesu nie
zamienia operacji w sukces z niekompletną telemetrią.

[Dowód komponentu](ai09-source-live-progress.json) zawiera 11 końcowych
kontroli. Obejmują pełne 58 tabel ordinary Source wraz z natywnym writerem
i readerem oraz pełne porównanie tabel i kontekstu wariantów demand/physical
z oryginalnym procesem. Zachowano wcześniejsze 56 kontroli ordinary/planned,
eksportu i planów prognozowania. Nie uruchomiono nowej diagnostyki canonical,
fitów projektu ani odczytu świeżego final testu. Checkpointy i wznowienie
pozostają osobnym, niezakończonym zakresem po stronie AI.
