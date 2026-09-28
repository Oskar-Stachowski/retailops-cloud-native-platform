# 02. Napraw generator i dane sprzedażowe

**Status: w realizacji. Repo: RetailOps. Zależność: 01.**

Obecny fundament danych: [DATA-01 — konfiguracja i identity](../../../evidence/ai/02/data01/README.md)
oraz [DATA-02 — wymiary, lifecycle i kalendarz](../../../evidence/ai/02/data02/README.md),
a także [DATA-04 — ceny i promocje](../../../evidence/ai/02/data04/README.md).
[Popyt/panel/koszyki](../../../evidence/ai/02/demand-panel/README.md) mają własny
odbiór źródła 2.3 i cech AI 3.0. [DATA-03](../../../evidence/ai/02/data03/README.md)
kwalifikuje chronologię, zwroty, gross/net oraz history/return-tail cutoffy źródła 2.4.
Poniżej pozostała praca: izolacja truth i końcowy odbiór źródła.

Cel: uzyskać deterministyczny, kompletny i spójny zbiór obserwowanej sprzedaży, który można eksportować i użyć w pierwszym forecastingu. Pełny ledger jest etapem 06. W tym etapie inventory, stockout i lost-sales nie są wiarygodnymi cechami ani labelami modelu.

Przeczytaj [architekturę](../architektura.md), [dane i czas](../kontrakty/dane-i-czas.md), [profile i bramki](../kontrakty/profile-i-bramki.md), wyniki audytu 00 i ustalenia kompatybilności 01. Główne miejsca do sprawdzenia: `data/generator/main.py`, `profile_engine.py`, `pricing.py`, `manifest.py`, `quality.py`, `realism_report.py`, `csv_writer.py`, `data/contracts/`, oraz użycie danych przez istniejące `ml/features/`.

## Kolejność małych PR-ów

6. **Separacja i bramki źródłowe.** Rozdzielić pozostałe parametry symulacji products/stores od źródłowych faktów. Domknąć granicę dostępu procesu feature buildera i runtime do truth oraz kontrolę dozwolonych wejść. Zakończyć quality/realism/readiness reports per use case; każdy wynik ma policy version, sample size, wartości, status i evidence. Zachować wykonywalne bramki, JSON/MD i nonzero exit dla obowiązkowych błędów; odbiór pełnego źródła wymaga aktualnych dowodów i zgodnego demo.

## Kontrakty i zakres pierwszego wariantu

Nowy `daily_demand_observations` ma grain `business_date/product_id/selling_location_id/channel` oraz `observed_units`, `observed_orders`, gross/net revenue, currency, realized price, promotion reference, return units, availability i quality/completeness status. Zrealizowana cena pozostaje obserwacją — nie wolno użyć jej jako wejścia do prognozy tego dnia. Feature builder dopuszcza plan ceny/promocji znany w origin.

Nie zaliczać legacy inventory jako gotowego tylko dlatego, że pliki istnieją. Do wariantu forecast-only dopuścić wyłącznie historię sprzedaży, kalendarz, prawidłowe wymiary i plany znane w origin. `inventory_ready=false`, `stockout=not_ready`, `anomaly=not_ready`; inventory feature columns nie są zerowane, lecz pomijane z wersji schematu. Stara heurystyka demo może pozostać jawnie odseparowana. Nowy forecast ma `target_type=observed_sales_units`, bez obietnicy przewidywania latent demand.

## Kontrole wymagane i negatywne

- Dwa identyczne uruchomienia dają te same logical IDs i dane; zmiana seed/liczby produktów/daty/treści zmienia właściwe ID. Sprawdzić również przyszłą tożsamość feature datasetu — stary algorytm ID nie może pozostać w nowej ścieżce.
- Calendar coverage wynosi 100% poprawnych kombinacji; usunięcie jednego obowiązkowego dnia nie jest interpretowane jako zero. Dodana sprzedaż przed launch/po discontinue jest odrzucana.
- Przykłady braku ceny, overlap ceny, innego rabatu transakcyjnego i nieaktywnej promocji celowo powodują failed gate.
- Powtórzony SKU, suma zamówienia różna od pozycji, nadmiarowy zwrot, sale przed order i return przed sale powodują failed gate.
- Timestampy UTC/DST i effective/available time mają testy granic; późna korekta nie zmienia historycznej wiedzy.
- W źródle można mieć truth, ale próba podania jej do features lub runtime failuje. Future inventory fallback jest usunięty albo zablokowany w ścieżce używanej przez AI; późniejszy snapshot nie zastępuje missing history.
- Zachować istniejące 15 strukturalnych checks i testy seed/demo API. Nie utożsamiać starych zielonych wyników z pełnym ML readiness.

## Artefakty i Definition of Done

Wersjonowane config/schema/manifest v2, generators/adapters, quality policies, passing/failing fixtures, raport dwóch runów `ai-smoke` i `ai-temporal-smoke`, tabela zmian kontraktów oraz dokładne odtworzone polecenia. Nie commitować dużych danych z CI. Spis poleceń zawiera tylko rzeczywiście zaimplementowane CLI; nazwy modułów z planu są propozycjami do zweryfikowania.

Etap kończy się, gdy panel, cena/promocja, chronologia, truth separation i identity przechodzą hard gates, demo działa, a niegotowe use cases mają uczciwe statusy. Następny etap: [03 — snapshot i curated](03-snapshot-curated.md). Pełny inventory jest rozwijany w [06](06-inventory-ledger.md), nie blokuje pierwszego slice forecastowego.

## Prompt dla Codex

```text
W repo retailops-cloud-native-platform wykonaj etap 02 z etapy/02-dane-sprzedazowe.md.
Najpierw przeczytaj README.md, architektura.md, kontrakty/dane-i-czas.md,
kontrakty/profile-i-bramki.md oraz evidence etapów 00 i 01.
Potwierdź rzeczywiste pliki/CLI i stan brancha. Realizuj opisane małe PR-y po kolei.
Zachowaj demo, źródłową własność generatora oraz manifest v2 i identity z DATA-01.
Kontynuuj od izolacji truth i końcowych bramek/readiness źródła.
Zachowaj bramki DATA-03, dojrzałość okien i history/return-tail cutoffy.
Zachowaj pełny panel, dzienne budżety,
koszyki bez powtórzeń oraz cechy AI 3.0.
Zachowaj resolver znanych planów i bramki cen/promocji z DATA-04.
Oddziel simulation truth. Pierwszy wariant jest forecast-only bez inventory features;
nie ogłaszaj gotowości stockout ani anomaly przed ich etapami.
Wdrażaj wymagane passing/failing checks i generuj tylko ograniczone fixtures.
Nie wykonuj wdrożenia cloud. Zapisz zmiany, migracje, wykonane polecenia, wyniki i
readiness per use case według szablony/karty-i-evidence.md. Nie oznaczaj założeń jako testów.
```
