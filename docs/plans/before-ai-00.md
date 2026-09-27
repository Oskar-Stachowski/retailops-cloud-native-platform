# Przygotowanie przed etapem AI 00

Aktualizacja: **2026-09-27**. To skrócona lista otwartych prac w istniejącym
RetailOps przed planowanym przejściem do rozbudowy AI. Szczegółowe kryteria
odbioru zawierają [otwarte ustalenia audytowe](../audits/open-findings.md).
[Ocena ML](../evidence/ml/fixed-origin-rf-2026-09-27/README.md) ma osobny
datowany raport i decyzję `rejected`.

Sam [etap AI 00](ai/etapy/00-audyt.md) jest audytem i **nie ma formalnych
zależności**. Można rozpocząć go wcześniej; nie wymaga zamknięcia wszystkich
ustaleń poniżej.

## Poprawki zalecane przed intensywnym testowaniem

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
