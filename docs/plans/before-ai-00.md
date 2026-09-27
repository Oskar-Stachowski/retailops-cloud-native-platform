# Przygotowanie przed etapem AI 00

Aktualizacja: **2026-09-27**. Nie ma otwartych prac przygotowawczych przed AI 00.
Aktualnym punktem odniesienia jest [audyt AI 00 na `cbf28b2`](../evidence/ai/00/README.md).
Następna instrukcja to **[AI 01](ai/etapy/01-fundament-projektu.md)**.

Warunki dalszych etapów i zakres pierwszych PR-ów są w jednym
[backlogu AI](ai/backlog.md), a potwierdzone problemy i kryteria zamknięcia
w [otwartych ustaleniach](../audits/open-findings.md).

Wyniki potrzebne do bieżącej oceny możliwości: [RF z decyzją `rejected`](../evidence/ml/fixed-origin-rf-2026-09-27/README.md)
oraz [izolacja seeda w PostgreSQL](../evidence/pre-ai-00/2026-09-27-seed-isolation.md).
Odrzucony RF nie jest dopuszczony do serving. Nowe dane i modele przechodzą
własne bramki AI 02–05; pełny ledger, streaming i AWS mają osobne etapy.
