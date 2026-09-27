# Lokalna polityka dopuszczania prognozy RF

Wersja `retailops-forecast-local-v1` jest zamrożona w
[`forecast_admission_v1.json`](../../ml/policy/forecast_admission_v1.json). Dotyczy
wyłącznie syntetycznej oceny RF w istniejącym RetailOps. Progi przyjęto dla
tego lokalnego kroku przed świeżym eksperymentem; zmiana progu
wymaga nowej wersji polityki i osobnego przeglądu przed użyciem testu końcowego.
Jej hash SHA-256 i wynik każdego warunku trafiają do `metrics.json`, metadanych
RF oraz karty modelu.

`candidate` oznacza zgodę na dalszą **lokalną walidację**. Nie oznacza
`approved`, wdrożenia ani dopuszczenia do serving. Każdy warunek jest wymagany;
`failed`, `not_ready` i `not_evaluable` dają `rejected`. Jest to poprawny wynik
eksperymentu, a nie powód do zmiany progów po zobaczeniu testu.

| Warunek | Reguła lokalna |
|---|---|
| Protokół | Trzy chronologiczne okna walidacyjne i rozłączny test z ustalonego origin, bez użycia testu do selekcji; liczby, klucze i metryki zgodne z prognozami RF i baseline |
| Pokrycie | 100% kwalifikujących się rekordów ocenione w każdym oknie; puste okno blokuje |
| Jakość | WAPE RF co najmniej 5% względnie lepsze od baseline na końcowym teście; metryki muszą być ocenialne |
| Stabilność | Niższe WAPE RF w co najmniej dwóch z trzech ocenialnych okien walidacyjnych |
| Segmenty | Dla każdego sklepu i kanału w teście co najmniej 20 rekordów, MAE RF najwyżej 5% większe od MAE baseline |
| Odtwarzalność lokalna | Snapshot źródeł zgodny z sumami oraz zapisany i ponownie odczytany model dają te same prognozy testowe co model przed zapisem |

Test sklepu i kanału jest z góry określony dla obecnego panelu. Kategorie,
scenariusze, wiele seedów, osobny powtórzony trening, kalibracja, drift i budżety
zasobów są częścią szerszych etapów AI lub świeżego odbioru eksperymentu, a nie
tej lokalnej etykiety. Żadnego z tych dowodów nie należy przedstawiać jako
spełnionego przez sam status `candidate`.

Ścieżka baseline (`make ml-metadata`, `ml-inference`, `ml-metrics`) może zapisać
jedynie `experimental`, `rejected` lub `retraining_required`; argument CLI nie
może nadać jej `candidate` ani `approved`. RF wylicza decyzję z danych, protokołu
i zapisanego artefaktu; ręczna zmiana pola statusu w kodzie budującym metadane
jest odrzucana. Historyczne snapshoty zachowują dawne znaczenie statusów i nie
są przeliczane według tej wersji.
