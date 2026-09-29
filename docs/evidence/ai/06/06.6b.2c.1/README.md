# AI 06.6b.2c.1 — snapshot i typed import inventory

Lokalny odbiór na Darwin/ARM64, 29.09.2026. [Wyniki](verification.json) wiążą
kod obu repo z nowymi source → qualification → snapshot IDs.
RetailOps: `6b40f11086dc810d31a79bf6c0e6483a5834ed23` na `ai/06-01-inventory-ledger`.
AI: `891a7615466e467e1a37454a0f2af5a464605bbd` na `ai/06-inventory-handoff`, w osobnym worktree.
To odbiór eksportu/importu; curated, domyślne przełączenie i model 08 pozostają otwarte.

## Wynik

Oba standardowe profile mają świeże powtórzenia z identycznymi trzema IDs
oraz snapshot descriptors. Źródło i kwalifikacja nie są zmieniane przez eksport.
Import, reimport i odczyt zachowują bajty wejścia i nie nadpisują publikacji.
Każdy przebieg obejmuje generację, qualification, export oraz import/reimport/verify.
Limit wynosi 300 s i 1024 MiB; tabela podaje sumę czasów etapów i maksimum RSS procesów.
Nie obejmuje instalacji zależności ani pending curated; nie jest pełną bramką DATA-06.

| Przebieg | Sekundy | Peak RSS MiB | Wiersze 43 tabel |
|---|---:|---:|---:|
| ai-smoke-first | 66.82 | 215.36 | 31729 |
| ai-smoke-repeat | 66.43 | 214.48 | 31729 |
| ai-temporal-smoke-first | 178.45 | 286.75 | 56533 |
| ai-temporal-smoke-repeat | 163.32 | 311.61 | 56533 |

**ai-smoke**

- Source: `source-sha256-52cdf90535820a2adebd999678758ec805f94f5254728706d73b0aabe819975e`
- Qualification: `inventory-labels-sha256-7800448cb678b43606e127771eecd3d6947a5d5bccc53dc04c9653b8f17cf447`
- Snapshot: `snapshot-sha256-07fd4d0ab12321983e7f64d446c4b72168b9734ad72d81cc0313a828a6929ac9`
- Mature labels: 250 dodatnich, 337 ujemnych.

**ai-temporal-smoke**

- Source: `source-sha256-df5364bc1773061d5f6bbe098336082949704fcda3a1dbc81fc9002ba23736a6`
- Qualification: `inventory-labels-sha256-9c1d0119a0f7b4ec450513c8a184794e0e4dc7c217eb690c8f0318f3ab72f981`
- Snapshot: `snapshot-sha256-0528ffabe3b476d2fb59894ce44e8ad0387304cd601f4315b5c5e35ade5d02a5`
- Mature labels: 472 dodatnich, 611 ujemnych.

## Zakres kontroli

- 43 worker facts/plans i 12 private evaluation tables; qualification JSON tylko
  po explicit opt-in w osobnym `evaluation_truth/qualification`.
- Typed Arrow, nulle, integer/bool/date/UTC/money, grain/ranges i source content hashes.
- Eksporter zabezpiecza source w private staging, ponownie liczy wszystkie 36 gates
  na tej kopii i rekwalifikuje okna z tych zweryfikowanych tabel. Wyeliminowano dwa
  redundantne przeliczenia source po nieudanej pierwszej próbie bramki budżetu.
  Kontrole integrity i recomputation pozostają; test potwierdza jeden pełny odczyt.
- Konsument nie importuje kodu generatora. Sprawdza reviewed schemas i gate receipt,
  ponownie liczy typed/native hashes oraz uzgadnia ledger, known snapshots,
  historyczny routing, issues, sprzedaż, refund/restock i receipts.
  Nie symuluje ponownie całych 36 gates ani pełnej kwalifikacji labeli.
- Resealed semantic forgeries: zmienione saldo, ilość sale/commerce, refund,
  receipt i future route są odrzucane. Late-availability source jest blokowany
  przed publikacją. Uszkodzone/dodatkowe pliki i błędny lineage nie są publikowane.
- 727 testów RetailOps, 773 testy AI, Ruff/format i mypy. Wheel z packaged 1.1
  contracts odczytuje facts/private bez producer imports i contract checkout fallback.
- 84 frozen pliki RetailOps, 19 demo i 80 starych fixture/contracts AI są
  byte-identyczne z zapisanymi bazami. Czytniki source2.0–2.7 i snapshot 1.0 działają.

Raw receipts: `ci-cd/reports/data/ai06-06b2c1/optimized/`; XML i dodatkowe kontrole
mają ścieżki/hash w verification JSON. Zmiany są lokalne; brak nowego Linux/remote CI.

## Kolejny zakres

**06.6b.2c.2:** curated 1.1 z native grain, causal availability i historycznym
as-of; pełny source → qualification → snapshot → import → curated budget,
truth isolation i przełączenie domyślnego source AI. Curated1.0 odrzuca1.1 jawnym
kodem `inventory_curated_contract_not_yet_supported`. DATA-06 i readiness pozostają
otwarte. Oceny04/05 wymagają ponowienia na nowych IDs, a model 08 własnego odbioru.
