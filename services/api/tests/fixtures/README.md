# Eksport do testu zgodności wstecznej

`source_manifest_v2_0.zip` zawiera rzeczywisty eksport CSV, raporty i cechy DATA-01,
wygenerowane kodem z commita `4d57655` (generator 0.2.0, schemat źródła 2.0.0).
Parametry: `ai-smoke`, 3 dni, 2 produkty, 2 pary sklep/kanał, 2 magazyny,
seed 42; daty wynikają z końca profilu 2026-07-31.

Generator uruchomiono z archiwum `git archive`, bez katalogu `.git`, dlatego
manifest poprawnie deklaruje provenance Git `unavailable`. Identity nie jest
przepisywane na nowy schemat. Pliki są małe i wyłącznie syntetyczne.

`source_manifest_v2_1.zip` pochodzi z czystego kodu DATA-02, commit `a4ddc79`;
parametry ai-smoke: 3 dni, 8 produktów, 3 pary, 2 magazyny, seed 42.
Zawiera 26 CSV, raporty, source manifest 2.1 i feature sidecar.
Test odczytu zachowuje oba identity oraz relację parent, bez przeliczania ich
według bieżącego generatora 0.4.0.
