# Utrzymanie dokumentacji

Dokumentację dla ludzi przechowuj wyłącznie w `docs/`. Główny `README.md` jest
krótkim wejściem do tego folderu. Konfiguracja narzędzi, szablon PR, kontrakty
maszynowe i automatycznie generowane artefakty pozostają przy kodzie.

## Jedno miejsce dla każdej informacji

- `STATUS.md`: aktualne możliwości i granice projektu, z datą przeglądu.
- `audits/open-findings.md`: tylko nadal otwarte, potwierdzone problemy.
- `plans/`: praca do wykonania, zależności i kryteria odbioru; propozycja nie oznacza wdrożenia.
- `guides/`: codzienna obsługa i rozwój.
- `runbooks/`: procedury konkretnej operacji lub awarii.
- `reference/`, `architecture/`, `security/`, `governance/`: obowiązujące kontrakty, decyzje i zasady.
- `evidence/`: najnowszy potrzebny dowód dla danego twierdzenia, z datą i zakresem.

## Aktualizacja po zmianie

1. Sprawdź twierdzenie w kodzie lub w rzeczywistym wyniku polecenia.
2. Popraw właściwy dokument; unikaj osobnej notatki „status na koniec sesji”.
3. Po rozwiązaniu problemu usuń cały jego wpis z audytu oraz odpowiadające mu zadania planu.
4. Aktualne zachowanie opisz w instrukcji lub statusie. Nie zostawiaj list `zrobione`, `rozwiązane` ani zakończonych checklist.
5. Usuń zastąpiony dowód, gdy nowy potwierdza ten sam zakres. Nie zmieniaj dat ani wyników starych prób tak, aby wyglądały na nowe.
6. Sprawdź względne linki i komendy; wszystkie komendy zakładają katalog główny repozytorium, chyba że dokument wskazuje `cd`.

## Dowody i wyniki narzędzi

Przed zapisaniem dowodu podaj: UTC/datę, commit, komendę lub workflow, środowisko,
wynik, ograniczenia i ścieżkę artefaktu. Przegląd kodu nie zastępuje próby runtime.

`ci-cd/reports/` to ignorowany katalog roboczy narzędzi, a nie archiwum audytów.
Do `docs/evidence/` przenoś tylko mały, przejrzany i oczyszczony wynik potrzebny do
aktualnej dokumentacji. Nie publikuj sekretów, `.env`, pełnego state Terraform,
zrzutów bazy ani prywatnych parametrów konta. Generowane model cards i manifesty
w katalogach danych są artefaktami przebiegu, nie drugim zestawem instrukcji.
