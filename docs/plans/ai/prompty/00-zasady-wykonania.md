# Wspólny prompt do pracy nad etapem

Użyj razem z jednym plikiem etapu i jego kontraktami. To instrukcja wykonawcza przyszłej pracy; nie uruchamia automatycznie wszystkich etapów.

```text
Pracujemy nad RetailOps Cloud-Native Platform i osobnym RetailOps AI Intelligence.
Realizuj wskazany etap z docs/plans/ai/.

1. Przeczytaj etap, jego zależności i powiązane kontrakty. Sprawdź aktualny commit,
   lokalne instrukcje repo oraz niezacommitowane prace. Ustal co istnieje, co wymaga
   modyfikacji, a co jest dopiero kontraktem docelowym. Nie zmieniaj cudzych prac.
2. Oprzyj wykonanie na rzeczywistym kodzie i zapisz jego SHA. Wnioski audytowe
   utrzymuj tylko wtedy, gdy nadal występują; naprawione usuń z aktywnej listy.
3. Wykonuj małe spójne fragmenty/PR-y. Zachowaj działające demo i wersjonuj zmiany
   kontraktów. Nie kopiuj generatora do AI ani nie współdziel operacyjnej bazy.
4. Utrzymuj point-in-time features, osobne simulation truth i labels, immutable
   dataset/model identity oraz poprawną semantykę zer i danych niekompletnych.
5. Wprowadź testy wymaganych zachowań i awarii. Nie traktuj brakującej próby,
   nieuruchomionego testu lub not_evaluable jako pozytywnego wyniku.
6. Zaktualizuj dokumentację, karty, konfigurację i monitoring wraz z zachowaniem.
   Nowe polecenia/API mają stać się działające; nie opisuj nieistniejących wyników.
7. Zapisz dowody: commit, config, dataset/split/model IDs, wykonane komendy,
   wyniki, ograniczenia i stan kryteriów odbioru. Wskaż następny odblokowany krok.
8. Zewnętrzne publikacje, migracje i cloud apply wykonuj tylko w zakresie
   uzgodnionego zadania. Sam prompt etapu projektowego nie oznacza polecenia
   uruchomienia płatnej infrastruktury ani wysłania czegokolwiek do innych osób.
```

Jeśli etap jest zbyt duży na jeden PR, zakończ spójny fragment z dowodami i jasno oznacz pozostały zakres. Nie obniżaj wymagań tylko po to, by oznaczyć etap jako ukończony.
