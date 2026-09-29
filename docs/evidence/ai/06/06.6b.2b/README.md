# AI 06.6b.2b — lifecycle i coverage inventory

**Odbiór lokalny 29.09.2026, branch `ai/06-01-inventory-ledger`, runtime `125219f`.**
[Rejestr](verification.json) przypina pełne SHA, komendy, parent/qualification IDs,
checksums, wyniki i środowisko macOS ARM64 / Python 3.11.15 / PyArrow 25.0.1.
[Kontrakt i uruchomienie](../../../../reference/inventory-label-qualification.md)
opisują source 2.7 i policy `active-physical-window-1.0.0`.

## Zakres

Osobny immutable private artefakt kwalifikuje **product × stock location × origin**
na podstawie zweryfikowanego source 2.7. Źródło i jego 58 tabel pozostają niezmienione.
Historyczny lifecycle/assortment/assignment/route, coverage tej samej fizycznej
pozycji od opening, pełny panel aktywnych kanałów i maturity warunkują label 0/1.
Okno obejmuje `(origin,origin+7 dni]`; kanały nie duplikują wspólnego stock.
Origin/window route IDs i coverage ID zapisują lineage.

Aktualny stockout ma `already_stockout` i null incident. Inactive, brakujące
lub niedostępne dane i niedojrzały tail mają `not_evaluable` i null label.
Brak popytu przy pełnym aktywnym oknie i dodatnim stock może dać negative;
zero sprzedaży nie daje positive. Kwalifikacja źródła wymaga obu klas i
source facts readiness. Nie kwalifikuje splitów, forecastów ani modelu 08.

## Świeże profile i kontrole

Oba pełne standardowe profile wykonano **dwukrotnie od świeżego generatora**
na czystym kodzie przypiętym do commita. W powtórzeniach są identyczne source
oraz qualification IDs/descriptors/artifacts/reports. Wszystkie 58 source CSV
i reports są byte-identical z odbiorem 06.6b.2a; świeże source IDs zmienia
rozszerzony fingerprint kodu. Frozen IDs i źródła nie są przepisywane.

| Profil | Wszystkie okna | Evaluable: positive / negative | Already stockout | Not evaluable | Czas obu pełnych przebiegów |
|---|---:|---|---:|---:|---|
| ai-smoke: 30 dni, 20 produktów, 3 stores, 2 stock | 1200 | 250 / 337 | 307 | 306 | 34,65 s / 36,51 s |
| ai-temporal-smoke: 102 dni, 8 produktów, 3 stores, 2 stock | 1632 | 472 / 611 | 432 | 117 | 100,59 s / 98,62 s |

Osiem rzeczywistych przypadków CLI obejmuje cztery powyższe przebiegi oraz:

- **Supplier-poor:** reliability 0 i mean lead 5; 10 positive / 5 negative,
  33 already stockout i 32 not evaluable. Kwalifikacja źródłowych klas przechodzi.
- **Zero opening:** 37 already stockout, 43 not evaluable, 0 labeli 0/1;
  globalna kwalifikacja `not_evaluable` przy braku klas.
- **Late availability:** source facts false, 47 origin-state-unavailable i
  1 outcomes-not-available. Jedno niezależne okno negative ma pełne własne dane,
  lecz globalna kwalifikacja źródła pozostaje `not_evaluable`.
- **No demand:** rzeczywisty jednodniowy source ma 0 arrivals/sales/episodes,
  dodatni stock i 1 immature window; 0 labeli 0/1. Nie dopisujemy negative do tailu.

Każda pełna ścieżka generator → source CSV → gates/readback → qualification
→ readback mieści się w **300 s / 1024 MiB**; maksimum 332,19 MiB.
To budżet lokalnego źródła i kwalifikacji; nie obejmuje exporter/importer/curated 03.

## Regresja i niezależny odczyt

**704 testy data/tests przechodzą, bez błędów i pominięć; 40 nowych.**
Ruff check/format przechodzą; mypy obejmuje 45 runtime/acceptance files.
Checked-in schema odpowiada wykonywanemu modelowi.

Testy obejmują historyczny lifecycle niezależny od bieżącego statusu,
launch/discontinue w origin i w oknie, brak/koniec assortment, route gaps/switches,
late metadata, brak kalendarza, brak/krótki/obcy/niedostępny stream certificate,
brak/incomplete/late panel i wspólny stock wielu kanałów. Izolowany dojrzały
przypadek bez popytu ma negative i globalny brak klas; nie jest generowanym source.
Kontrola przyszłego ruchu poza horyzontem zachowuje snapshot i cały label;
niedostępny ruch z przeszłości zachowuje cechy origin i wyklucza label.

Czytnik ponownie weryfikuje parent source i jego 36 gates, wylicza wszystkie
qualified windows/report i porównuje descriptor oraz pełne canonical bytes.
Zmiana labelu lub raportu z przeliczonymi checksum i ID jest odrzucana.
Extra files, symlinks, truth w facts, fałszywe readiness i duplicate JSON
nie przechodzą. Reuse nie naprawia uszkodzonego artefaktu.

Demo i bounded legacy small zachowują po 17 CSV; 19 tracked demo files,
archiwa 2.0–2.5 z source/feature IDs i parent, fresh 2.6 z 46 gates, frozen 2.7
oraz handoff 03 są zgodne. **84 frozen files** (fixtures/archives i dwa kontrakty 03)
są byte-identical względem `68fe5d9`. Nowa kwalifikacja nie zmienia parent source.

## Aktualne granice

`source_ready=false`, `inventory_ready=false`, `model_ready=false`.
Oba standardowe source profiles mają kwalifikację lifecycle/coverage klas;
model 08 i temporal splits pozostają `not_evaluated`.
Raw reports 2.7 zachowują historyczne `not_evaluated`; aktualna kwalifikacja
jest osobnym artefaktem z parent ID. Generator/API/handoff nadal używają 2.6.

Następny 06.6b.2c rozszerzy exporter/importer/curated 03 dla source 2.7 i jawnej
evaluation qualification 1.0, odbierze nowy snapshot, parent lineage, typed parity,
truth isolation, powtórzenia i pełny cross-repo budget oraz przełączy domyślne AI.
DATA-06 pozostaje otwarte. Następnie trzeba ponowić 04/05 na nowych IDs;
nie przenosimy wcześniejszych metryk ani nie trenujemy modelu 08 w tym odbiorze.

Repo AI i worktree AI 12 nie były modyfikowane. Commity są lokalne;
nie wykonano nowego Required CI ani publikacji AI 06 na main/origin.
Pełne dane/JUnit/receipts pozostają pod ignorowanym
`ci-cd/reports/data/ai06-06b2b/final/`; Git przechowuje mały rejestr i dokumentację.
