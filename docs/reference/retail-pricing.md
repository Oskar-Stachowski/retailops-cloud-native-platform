# Ceny i promocje profili AI

[Profile](data-profiles.md) · [Wymiary](retail-dimensions.md) · [Generowanie](../guides/data.md)

Profile `ai-*` używają jednego [resolvera](../../data/generator/price_resolver.py)
opartego na jawnych planach. Generator 0.4.0 i source schema 2.2.0 dodają pięć
tabel do dziewięciu tabel wymiarów i 17 tabel legacy: razem 31 CSV.
Kontrakt `retail-pricing-1.0.0` ma [JSON Schema](../../data/contracts/retail_pricing.v1.schema.json)
oraz [wykonywalne kontrole](../../data/generator/pricing_quality.py).
Demo i profile small/medium/large zachowują wcześniejsze reguły i bajty CSV.

| Tabela | Znaczenie |
|---|---|
| `price_plans` | Cena regularna produktu, scope, okres i wersja, currency, known/available time. |
| `promotion_plans` | Kampania i jej rewizje: typ, scope, okres, rabat, minimalna ilość, priority/status i known/available time. |
| `sale_price_references` | Jedna referencja na sale: order item, fizyczna selling location, kanał, dzień, cutoff wyceny i wybrane plan IDs. |
| `daily_price_observations` | Sparse wynik transakcji na dzień/produkt/selling location/channel: quantity, gross revenue, realized price, availability i plan IDs. |
| `promotion_effect_truth` | Osobna simulation truth: okna pre/during/post i mnożnik popytu każdej wersji kampanii. |

## Rozstrzyganie znanego planu

Wywołanie `PriceResolver.resolve(product_id, location, channel, day, as_of_time, quantity)`
zwraca cenę regularną, jednostkową po rabacie, sumę linii, currency oraz wybrane IDs.
Business date jest datą UTC, a cutoff wymaga jawnej strefy. Resolver nie potrzebuje
tabeli truth; korzysta wyłącznie z planów ceny i promocji.

Okres jest półotwarty: `effective_from <= day < effective_to`. Plan jest znany,
gdy `available_at <= as_of_time`; `known_at <= available_at`. Dla tego samego
klucza i identycznego okresu wybiera się najwyższą znaną wersję. Rewizje mają
rosnący czas dostępności. Nakładające się różne okresy tego samego klucza są błędem.
Późniejsza korekta nie zmienia odpowiedzi przy wcześniejszym cutoff.

Scope ceny ma jawne pierwszeństwo:

1. `location_channel` — konkretna lokalizacja i kanał.
2. `location` — lokalizacja, kanał all.
3. `channel` — kanał, pusta lokalizacja.
4. `global` — pusta lokalizacja, kanał all.

Uwzględnia się tylko plany znane w cutoff; nieznany override nie zastępuje
znanej ceny globalnej. Brak jakiejkolwiek znanej ceny lub niejednoznaczny wybór
kończy się błędem. Nie ma fallbacku do ceny transakcji albo losowego planu.

Generator tworzy dwie części historycznego planu (jedną przy jednym dniu),
z nową ceną +3% w drugiej części, i globalny plan na 14 dni po końcu historii.
Wersje są znane przed historią. Opcjonalne scope overrides mają współczynniki
0,97 dla kanału, 1,02 dla lokalizacji i 0,95 dla pary. To jawne syntetyczne
reguły, bez modelu VAT/FX; cały zbiór używa PLN, również dla lokalizacji DE-BE.
Plany mogą obejmować dni bez aktywnej sprzedaży; mianownik coverage wyznacza
asortyment i lifecycle, także w dni zamknięcia.

## Promocje i kwoty

Kampanie mają różne daty i scope. Co piąty produkt nie ma promocji.
Każda kampania ma dwie jawne rewizje znane przed początkiem historii:
pierwszą z rabatem o 2 punkty procentowe niższym oraz drugą zgodną z tabelą.
Cancellation jako najnowsza znana rewizja wyłącza kampanię; nie przywraca starszej.

| Typ | Rabat drugiej wersji | Minimalna ilość linii |
|---|---:|---:|
| percentage | 8% | 1 |
| bundle | 15% | 2 |
| clearance | 25% | 1 |
| seasonal | 12% | 1 |

Bundle oznacza próg ilościowy: po osiągnięciu dwóch sztuk rabat obejmuje **całą
linię**. Nie jest to buy-X/pay-Y ani koszykowy pakiet różnych SKU. Dla ilości 0
nie stosuje się promocji. Priority rozstrzyga spośród aktywnych, znanych,
pasujących do scope i ilości kampanii. `exclusive_highest_priority` wybiera jedną;
rabaty się nie składają. Remis najwyższej priority jest błędem.

Kwoty używają Decimal i ROUND_HALF_UP: najpierw unit price do dwóch miejsc,
potem total = quantity × zaokrąglona unit price, do dwóch miejsc.
Ta sama wycena zasila order item i sale, a suma linii order total.
Każda sale wskazuje właściwą pozycję, price plan i opcjonalną promotion revision.
Cutoff wyceny jest równy `ordered_at`; poprawa relacji ordered/sold/returns
pozostaje osobnym zakresem chronologii.

## Obserwacje i truth

Daily realized price jest quantity-weighted: sum(gross revenue)/sum(quantity).
Przy quantity 0 realized price pozostaje pusty. Availability to maksimum
`sale.ingested_at` (lub sold_at) oraz cutoffów wyceny zamówień.
To wynik zaobserwowanych transakcji, **nie plan ani cecha znana przed target day**.
Tabela jest sparse; nie zastępuje przyszłego pełnego panelu demand i kompletności.
Obecne cechy schema 2.0 nie zawierają realized price, revenue ani promotion truth.
Ich generator weryfikuje bramkę cenową, a parent identity obejmuje pełne źródło.

Truth stosuje chronologiczne okna względem realnych dat kampanii:
pre = trzy dni przed startem (0,92), during = okres promocji (1,20/1,15/1,30/1,25
według typu), post = cztery dni po wyłącznym końcu (0,86).
Generator uwzględnia znaną wersję i scope kampanii; w during dodatkowo używa
syntetycznej promo sensitivity miejsca. Przy kilku sąsiednich efektach during
ma pierwszeństwo, potem priority i stabilny plan ID.
Efekt opisuje oddziaływanie kampanii niezależnie od tego, czy konkretna linia
bundle osiągnęła próg ilościowy. Próbkowanie ilości i jego kalibracja są dalszą
pracą demand; nie ma iteracyjnego sprzęgania koszyka z rabatem bundle.

AI sales zachowuje legacy nagłówek `promotion_uplift`, ale jego wartości są
puste; pre/post/during multiplier znajduje się w osobnej tabeli sklasyfikowanej
`simulation_truth`. Inne legacy latent/noise/stockout fields nadal czekają na
separację DATA-05. Ten zakres nie oznacza pełnej izolacji truth/runtime.

Legacy price_history/promotions są projekcjami kanonicznych planów.
Ich końce dat pozostają włączne (exclusive end minus dzień), lecz stare kolumny
nie mieszczą pełnego scope/availability. Do nowych zastosowań AI czytaj kanoniczne
plany, nie te uproszczone widoki. Historyczne eksporty 2.0 i 2.1 zachowują własną
semantykę i identity; nowy odczyt je waliduje, bez przepisywania wersji.

## Bramki i readiness

Sześć hard gates sprawdza schema/FK/scope/wersje, 100% znanych cen i
jednoznaczną priority dla ważnych dni asortymentu, zgodność transakcji i referencji,
uzgodnienie agregatów, adapter oraz kierunek truth. Są dodatkiem do ośmiu bramek
wymiarów i 15 istniejących kontroli strukturalnych.
Wyniki JSON i krótkie MD trafiają do pricing_report i są objęte checksumami v2.
Odczyt źródła odtwarza bramki i oba raporty; przeliczenie hashów błędnych danych
nie omija kontroli. Generowanie, feature builder i validator odrzucają błędy.

Source schema 2.2.0, pricing policy oraz kanonizacja 1.2.0 wchodzą do identity.
Readiness forecasting/anomaly/stockout/replay nadal wynosi not_ready,
inventory_ready=false. Pełny panel, popyt/koszyki, chronologia/zwroty i pozostała
separacja truth wymagają dalszych prac etapu 02 przed nowym importem AI 03.
