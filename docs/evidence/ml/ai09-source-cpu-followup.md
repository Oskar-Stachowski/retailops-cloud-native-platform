# AI 09: koszt konwersji Arrow i aktywacja indeksu księgi

Dziewiąta rzeczywista diagnostyka development, run `37853501527`, zakończyła się
na limicie 3600 s bez ukończonej fazy. Próbkowany szczyt RSS wyniósł
9061416960 B przy zatwierdzonym limicie 12 GiB. Zachowano koszt i nieudane
artefakty. AI 07–08 pozostają zamknięte.

Profil CPU małego, wcześniej odsłoniętego Source wykazał wielokrotne sprawdzanie
typów tych samych schematów Arrow. Przegląd cached ledgeru ujawnił też brak
znacznika pełnej walidacji, który zwykły `InventoryLedger.from_payload` ustawia
po sprawdzeniu księgi. Z tego powodu istniejący indeks zapytań nie był używany
wewnątrz cached symulatora.

`inventory-source-cached-ledger-2.2.3` i `planned-source-cached-execution-1.1.3`
zawierają dwie poprawki:

- Niezmienny schemat Arrow korzysta z niezmiennego planu konwersji w cache
  ograniczonym do 128 schematów. Kontrola kolumn, null, Decimal i precyzji czasu
  pozostaje obowiązkowa. Niestandardowe i niehashowalne schematy zachowują
  leniwe przetwarzanie, także kolejność błędu pierwszej wartości przed odczytem
  następnego pola.
- Cached księga ustawia znacznik dopiero po wszystkich kontrolach ruchów,
  masterów, tożsamości, porządku, otwarć, transferów i sald. Istniejąca obsługa
  opóźnionej dostępności oraz pełny niezależny replay pozostają zachowane.
- Lokalny `api-coverage` jawnie wybiera branch coverage i konfigurację głównego
  `pyproject.toml`. Zapobiega to mieszaniu trybów procesu głównego i jego dzieci;
  istniejące CI używa tego samego trybu. Progi pokrycia pozostają zachowane.

[Oczyszczony dowód i koszty](ai09-source-cpu-followup.json) zapisują pierwsze
71 początkowych testów, 117 kontroli ordinary/demand/physical przed poprawką
leniwego odczytu oraz 72 kontrole końcowego kodu. Kontrola procesu głównego
i dziecka potwierdza zgodny branch coverage. Trzy świeże pary końcowego kodu
zachowały wszystkie 58 tabel, context, CSV i oba natywne raporty. Mediana CPU
całego przygotowania spadła o 3,46%, wall o 3,54%; wall samego readera o 2,22%.
Zachowano też wcześniejsze trzy pary: CPU −3,83%, wall −4,14% oraz wzrost wall
readera o 3,72%.
Pomiar obejmuje także niezależne porównanie danych. Profilowanie CPU było
osobnym narzędziem audytu; jego narzutu nie odejmowano z pomiarów profilu.

Lokalny pełny `make ci-local` zachował 1043 passed, 4 failed i 143 skipped.
Cztery błędy dotyczą izolowanego runtime przy niedostępnym Dockerze; raport
pokrycia zakończył się błędem mieszania trybów. Wynik jest zachowany w dowodzie,
bez uruchamiania usług użytkownika ani zastępowania izolacji wykonaniem na hoście.

Te małe pary nie określają czasu pełnego profilu canonical ani zysku
pamięci na dużym Source. Pełny chroniony odbiór dokładnego head
i wynikowego main oraz nowa zamrożona receptura w repo AI pozostają wymagane.
Nie wykonano nowej diagnostyki canonical, projektowego fitu, inicjalizacji
dziennika ani odczytu świeżego final testu. Kontrakty Source/snapshot i budżety
pozostają zachowane.
