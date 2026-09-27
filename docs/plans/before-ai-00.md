# Przygotowanie przed etapem AI 00

Aktualizacja: **2026-09-27**. To skrócona lista otwartych prac w istniejącym
RetailOps przed planowanym przejściem do rozbudowy AI. Szczegółowe kryteria
odbioru zawierają [otwarte ustalenia audytowe](../audits/open-findings.md).
[Ocena ML](../evidence/ml/fixed-origin-rf-2026-09-27/README.md) ma osobny
datowany raport i decyzję `rejected`.

[Audyt przygotowań z 27.09.2026](../evidence/pre-ai-00/2026-09-27-readiness.md)
potwierdza możliwość rozpoczęcia AI 00 na `4da25cb`. Nie potwierdza pełnego
zamknięcia przygotowań: izolacja bazy testu seeda wymaga poprawki OPS-04.

Sam [etap AI 00](ai/etapy/00-audyt.md) jest audytem i **nie ma formalnych
zależności**. Można rozpocząć go wcześniej; nie wymaga zamknięcia wszystkich
ustaleń poniżej.

## Pozostały zakres

| Praca | Kiedy jest wymagana |
|---|---|
| OPS-04: wyeliminować nadpisanie izolowanej bazy przez `dbname` w query URL | Przed poleganiem na izolacji seeda na serwerze z wartościowymi danymi; najbliższa poprawka w RetailOps. |
| ML-07: zachować historyczne wersje agregatów przy spóźnionych danych | AI 02–04, przed odbiorem importu i cech zgodnych ze stanem wiedzy w origin. |
| OPS-03: trwałe ACK/DLQ bez utraty zdarzenia; OPS-07: jeden zgodny kontrakt zdarzeń | AI 10, przed odbiorem integracji strumieniowej. |
| OPS-06: przypiąć wejścia builda i workflow | Nowe repo AI od 01; istniejące obrazy/workflow przed wydawaniem i wdrożeniami w 14–15. |

Kryteria i dowody są w [audycie](../audits/open-findings.md). Pełne AI 00
nadal trzeba wykonać według jego instrukcji; ten przegląd przygotowań go nie
zastępuje. Dalej obowiązują bramki źródła w 02, eksportu/importu w 03,
oceny w 04 i lifecycle/serving w 05. Odrzucony RF nie może zostać championem;
baseline może zostać wybrany dopiero po ocenie na nowych danych.

AWS/EKS, Helm, MLflow i pełny ledger zapasów mają własne etapy rozwoju;
ich wdrożenie nie jest wymagane przed tym audytem.

Po wykonaniu zadania usuń jego wpis z tej listy i odpowiedniego planu lub audytu,
a aktualne zachowanie opisz we właściwej instrukcji. Nie pozostawiaj
zakończonych pozycji z dopiskiem „zrobione” lub „rozwiązane”.
