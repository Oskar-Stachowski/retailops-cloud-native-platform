# AI 09: indeksy zapytań i niezależna weryfikacja dzienna

Rzeczywista próba development 1.8 w repozytorium AI (`37824794411`) osiągnęła
limit 3600 s przy limicie RSS 12 GiB. Próbkowany szczyt RSS wyniósł
9066307584 B; nie ukończono żadnej z pięciu faz. Próbki stosów oraz odczyt kodu
wskazały powtarzane skanowanie ruchów w zapytaniach o saldo, diagnostyce
stockout i dziennej rekonsyliacji. Stosy nie wskazują właściciela alokacji.

Implementacje `inventory-source-cached-ledger-2.2.2` i
`planned-source-cached-execution-1.1.2` obejmują:

- Jednorazowe grupowanie ruchów i odczyt jednostek dla ksiąg po pełnej
  walidacji payload. Ręcznie utworzone i zastąpione księgi korzystają z
  dotychczasowego przeglądania wejść.
- Prefiksy sald fizycznych oraz chronologicznej wiedzy z dokładnymi granicami
  czasu. Nieregularna kolejność dostępności zachowuje pełny natywny replay,
  w tym oryginalną kolejność błędów. Znane zero i nieznane otwarcie pozostają
  różnymi wynikami.
- Prefiksy fizycznych okresów w produkcji. Niezależny verifier buduje własne
  koszyki dzienne z każdego ruchu; sprawdza wszystkie wartości, lineage,
  pełne/niepełne dni, tożsamości i kompletność ziarna.
- Jawne przypięcia hashy całego zmienionego kodu zapytań, snapshotów i projekcji.

274 kontrole końcowego kodu przeszły. Obejmują oryginalne granice fizyczne
i knowledge, opóźnione otwarcia/przyjęcia, partial days, mutable replacements,
wszystkie 58 tabel/CSV oraz niezależny replay demand/physical. Mypy zaliczył
43 skonfigurowane pliki i dwa nowe moduły; Ruff i format 160 plików są poprawne.

[Dowód i koszty](ai09-ledger-query-index.json) zawierają trzy świeże pary
procesów małego pełnego build oraz trzy pary rzeczywistych czterech jąder
na małym, długim kontrolnym Source. Zachowują wszystkie hashe tabel, context,
sald, fizycznych okresów i snapshotów. Zapis obejmuje także koszty pamięci
oraz wcześniejsze pomiary częściowej poprawki. Wyniki tych kontroli nie
kwalifikują pełnego profilu canonical ani całej kampanii naukowej.

Dokument zapisuje przygotowanie przed odbiorem całego Required CI końcowego
head i wynikowego main. Kolejna zamrożona receptura wymaga także odbioru zmian
w repozytorium AI. Nie wykonano nowej próby canonical, projektowych fitów,
inicjalizacji dziennika ani odczytów świeżego final testu. AI 07–08 pozostają
zamknięte. Otwarte sesje i usługi użytkownika pozostają nienaruszone.
