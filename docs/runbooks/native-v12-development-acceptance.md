# Oryginalny v12 w integracji AI 10

Ta ścieżka używa oryginalnego zamrożonego v12, który ma ocenę jakości
`not_ready`, i nie zmienia tej oceny. Dokładny dokument właściciela pozwala
na użycie deweloperskie. Osobna przestrzeń modelu to
`retailops-demand-forecast-v12-development`; standardowa przestrzeń i fixtures
mechaniczne nie dziedziczą tego uprawnienia.

1. Użyj izolowanego workflow AI `AI10 original v12 native output`. Lokalny
   Docker nie jest potrzebny. Workflow musi wskazać dokładne SHA obu repozytoriów
   i tymczasowy handoff z prawem S3 GET; jego signed URLs nie trafiają do repo,
   stdout ani artefaktów.
2. Odtwórz wszystkie 664 oryginalne pliki i dokładny wheel z zamrożonym lockiem.
   Oryginalny verifier sprawdza cały eksport, nie tylko wybrany recipe. Wybór
   `seed-720001/rolling-03` jest jawny; nie wybieraj recipe według nowych metryk.
3. Przygotuj nowy kompletny snapshot Source: 43 tabele, profil
   `ai-temporal-smoke`, seed 42, 102 dni historii i 14 dni planów, bez truth.
   Oddziel go od oryginalnych danych treningowych. Aktualny importer AI buduje
   zweryfikowane curated/features i 56 wierszy dla czterech szeregów store.
4. Wykonaj pełną kwalifikację nowych wejść i dwa niezależne cold predictions.
   Wszystkie dziesięć review gates musi mieć rzeczywiste dowody; bramka segments
   oznacza zaakceptowany zakres development, a nie nową naukową kwalifikację.
5. Zaimportuj pełny kampanijny eksport do rzeczywistego MLflow z HTTP checksum
   wszystkich plików. Shared-inode scratch na własnym tymczasowym runnerze
   ogranicza miejsce na dysku; nie jest osobnym backupem. Oryginały w S3 są
   niezmienione. Zarejestruj i promuj tylko osobną przestrzeń development.
6. Przed przyjęciem zadania wykonaj pełny preload. Nie zwiększaj limitów lease,
   zadania ani workera, aby pomieścić długą weryfikację archiwum. Następnie
   wykonaj rzeczywisty cold worker i atomowy zapis publication/outbox. Błąd
   enqueue ma cofnąć publication wraz z outboxem.
7. Zachowaj bazę AI podczas uruchomienia niezależnego odbiorcy Source. Odbiorca
   uruchamia rzeczywisty oryginalny publisher SQL z prywatnym control file,
   a następnie powtarza identyczne zdarzenia raz. Wszystkie 56 oryginalnych ACK
   musi mieć odpowiadające pozycje w Source checkpoint receipts.
8. Przygotuj prywatny head policy z całym oryginalnym census oraz rzeczywistym
   `owner-review.json`. Dla przestrzeni development review wymaga dokładnego
   `development_acceptance_sha256`, przypisanego do dokumentu właściciela.
   Sama zmiana nazwy modelu nie daje uprawnienia. Standardowe review zachowuje
   wcześniejszy zestaw pól. Policy jest create-only i ważna maksymalnie 15 minut.
9. Sprawdź cały payload każdego wyniku w rzeczywistym TCP API i w istniejącym
   built UI Forecasts: oryginalne mean/median/interval, closed-target nulls,
   native IDs, wszystkie lineage, 50/6 pagination, 401/403/422, live revocation
   i brak credentials w browser storage. UI pokazuje pierwotną ocenę
   `not_ready` oraz zakres development.
10. Dopiero po tych dowodach usuń kontenery/volumes z dokładnym własnym owner
    label. Zachowaj publiczne receipts i oryginalne wyniki, bez prywatnych
    control files lub signed URLs. Po wykonaniu usuń tymczasowy sekret GitHub
    i dokładnie własne pomocnicze obiekty S3, zachowując oryginalne archiwum.

Dedykowany test:
`services/api/tests/test_native_forecast_output_durability.py`.
Bez oryginalnego outputu oraz działającej oryginalnej bazy AI test nie ma
fallbacku do fixture. `--setup-plan` sprawdza jedynie rejestrację fixtures,
a testy prywatnego policy nie są dowodem wykonania modelu.
