# Przygotowanie przed etapem AI 00

Aktualizacja: **2026-09-27**. To skrócona lista otwartych prac w istniejącym
RetailOps przed planowanym przejściem do rozbudowy AI. Szczegółowe kryteria
odbioru zawierają [plan oceny ML](ml-evaluation.md) i
[otwarte ustalenia audytowe](../audits/open-findings.md).

Sam [etap AI 00](ai/etapy/00-audyt.md) jest audytem i **nie ma formalnych
zależności**. Można rozpocząć go wcześniej; nie wymaga zamknięcia wszystkich
ustaleń poniżej.

## Ocena ML — główny pakiet przygotowawczy

1. [ ] **Identyfikacja eksperymentów** — osobne wersje przebiegów, zapis kodu,
   danych, parametrów, zależności i sum kontrolnych.
2. [ ] **Poprawne cechy** — usunięcie informacji z przyszłości, poprawne
   przypisanie zapasu do lokalizacji oraz rozróżnienie zerowej sprzedaży
   i brakujących danych. Cechy bez wiarygodnej dostępności w chwili prognozy
   należy wyłączyć.
3. [ ] **Poprawna ocena czasowa** — kalendarzowe lagi, prognoza całego horyzontu
   z jednego momentu, chronologiczna walidacja i osobny test końcowy. Model
   i baseline muszą korzystać z tej samej dostępnej wiedzy i ocenianych rekordów.
4. [ ] **Poprawne metryki** — zerowy mianownik lub brak danych nie mogą
   oznaczać idealnego wyniku ani pozwalać na pozytywną decyzję o modelu.
5. [ ] **Zasady dopuszczania modelu** — ustalone przed eksperymentem kryteria
   jakości, stabilności i odtwarzalności oraz uzasadniona decyzja `candidate`
   albo `rejected`, której nie można obejść ręcznym ustawieniem statusu.
6. [ ] **Spójna ścieżka modelu** — batch, metadane i metryki korzystają
   z dokładnie ocenionego artefaktu RF, bez cichego przełączenia na baseline
   lub ponownego treningu.
7. [ ] **Świeży eksperyment i odbiór** — porównanie z baseline, powtórzenie
   wyniku, testy negatywne w CI, datowany raport i zmiany na `main` przez PR.
   Rzetelne odrzucenie modelu również może zakończyć ten pakiet.

## Poprawki zalecane przed intensywnym testowaniem

- [ ] **OPS-01: zachowanie danych** — zatrzymywanie i ponowne uruchamianie
  Compose bez kasowania wolumenów i ponownego seeda; osobna operacja resetu.
- [ ] **OPS-02: granica lokalnego demo** — domyślny dostęp przez loopback,
  ponieważ przełączanie użytkowników demo nie jest uwierzytelnieniem.
- [ ] **OPS-04: izolacja testów seeda** — katalog tymczasowy i osobna baza,
  bez modyfikowania danych projektu ani bazy deweloperskiej.
- [ ] **OPS-05: bezpieczna diagnostyka** — brak haseł i pełnego `DATABASE_URL`
  w komunikatach oraz raportach testów.

## Pozostały zakres

Problemy potwierdzania offsetów i ACK/DLQ (OPS-03), przypinania zależności
builda i workflow (OPS-06) oraz zgodności kontraktów zdarzeń (OPS-07) pozostają
w [audycie](../audits/open-findings.md) do przypisania dalszym pracom.
Nie są formalnymi warunkami rozpoczęcia etapu 00.

AWS/EKS, Helm, MLflow i pełny ledger zapasów mają własne etapy rozwoju;
ich wdrożenie nie jest wymagane przed tym audytem.

Po wykonaniu zadania usuń jego wpis z tej listy i odpowiedniego planu lub audytu,
a aktualne zachowanie opisz we właściwej instrukcji. Nie pozostawiaj
zakończonych pozycji z dopiskiem „zrobione” lub „rozwiązane”.
