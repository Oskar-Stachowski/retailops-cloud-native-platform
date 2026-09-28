# 02 — Źródło sprzedaży AI

**Etap odebrany lokalnie. Repo: RetailOps. Zależność: 01.**

[Audyt gotowości](../../../evidence/ai/02/audit/README.md) potwierdza wejście do
AI 03 dla syntetycznej sprzedaży obserwowanej. [Odbiór źródła](../../../evidence/ai/02/data05/README.md)
obejmuje source 2.6, generator 0.8, kanonizację 1.6 i 46 hard gates.

Źródło obejmuje jawne profile/daty/identity, wymiary i kalendarz,
znane plany cen/promocji, pełny aktywny panel, budżety/koszyki,
chronologię sprzedaży/zwrotów, refundacje i osobny dojrzały ogon.
Parametry symulacji są poza faktami. Izolowany worker tworzy cechy 3.1
z czterech projekcji; pełny fingerprint wiąże wszystkie wykonywane pliki.
Wersje obserwacji zachowują wcześniejszy stan, a odczyt as-of nie widzi
późnych sprzedaży/korekt. Brak historii jest jawnie niedostępny.

Kontrakt: [odbiór źródła](../../../reference/source-acceptance.md).
Polecenia: [instrukcja danych](../../../guides/data.md).
Komponenty: [DATA-01](../../../evidence/ai/02/data01/README.md),
[wymiary](../../../evidence/ai/02/data02/README.md),
[ceny](../../../evidence/ai/02/data04/README.md),
[panel/koszyki](../../../evidence/ai/02/demand-panel/README.md),
[chronologia/zwroty](../../../evidence/ai/02/data03/README.md).
Demo i 15 pierwotnych checks zachowują zgodność; archiwa source 2.0–2.5
pozostają czytelne z identycznymi IDs.

`source_ready=true` kwalifikuje ograniczone profile do snapshotu
observed_sales_units. Forecasting/model serving, anomaly, stockout i pełny
replay pozostają not_ready; inventory_ready=false. Realism zachowuje jawne
progi i null/not_evaluable/not_ready przy niewystarczającej próbce.

Następny zakres: [03 — snapshot, importer i curated](03-snapshot-curated.md),
z typed Parquet i polityką artefaktów w RetailOps. Eksport/import muszą
zachować istniejącą historię wersji. Ledger rozwija [06](06-inventory-ledger.md).
Zdalny odbiór i zakres dalszych prac: [audyt](../../../evidence/ai/02/audit/README.md)
i [backlog](../backlog.md).
