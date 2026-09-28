# 02 — Źródło sprzedaży AI

**Etap odebrany lokalnie 28.09.2026. Repo: RetailOps. Zależność: 01.**

[Audyt gotowości do AI 03](../../../evidence/ai/02/audit/README.md) potwierdza
wejście dla bieżącej syntetycznej sprzedaży obserwowanej. Pełna historia korekt
ML-07 pozostaje otwarta; DATA-07 wymaga uzupełnienia fingerprintu workera przed
publikacją immutable snapshot w AI 03.

[DATA-05](../../../evidence/ai/02/data05/README.md) potwierdza source 2.5,
generator 0.7, kanonizację 1.5, 45 hard gates i izolowany worker cech 3.0.
Źródło obejmuje jawne profile/daty/identity, kanoniczne wymiary i kalendarz,
znane plany cen/promocji, pełny aktywny panel, dzienne budżety i koszyki,
chronologię sprzedaży/zwrotów, refundacje i osobny dojrzały ogon.
Parametry symulacji są poza faktami; runtime przyjmuje tylko trzy wąskie projekcje.

Aktualny kontrakt i granica procesu: [odbiór źródła](../../../reference/source-acceptance.md).
Wykonywalne polecenia: [instrukcja danych](../../../guides/data.md).
Dowody komponentów: [DATA-01](../../../evidence/ai/02/data01/README.md),
[wymiary](../../../evidence/ai/02/data02/README.md),
[ceny](../../../evidence/ai/02/data04/README.md),
[panel/koszyki](../../../evidence/ai/02/demand-panel/README.md)
i [chronologia/zwroty](../../../evidence/ai/02/data03/README.md).
Demo, 15 pierwotnych checks i odczyt source 2.0–2.4 są zachowane.

`source_ready=true` kwalifikuje ograniczone profile do pierwszego snapshotu
observed_sales_units. Forecasting/model serving, anomaly, stockout i replay
pozostają not_ready; inventory_ready=false i cechy zapasu są pominięte.
Realism ma jawne progi oraz null/not_evaluable/not_ready dla metryk,
których próbka lub źródło nie uzasadnia. To nie jest benchmark rynku,
dużych profili, inventory ledgeru ani dowód wdrożenia AI.

Następny zakres: [03 — snapshot, importer i curated](03-snapshot-curated.md),
z typed Parquet i polityką artefaktów w RetailOps. Historia korekt ML-07
pozostaje warunkiem pełnego replay w 03–04; ledger rozwija [06](06-inventory-ledger.md).
Nowe zmiany etapu 02 mają lokalny odbiór; zdalny Required CI nie był uruchomiony.
Otwartą pracę i zależności opisuje [backlog](../backlog.md).
