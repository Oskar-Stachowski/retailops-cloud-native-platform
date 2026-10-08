# AI 09 — source 2.8 z known plans i stabilny odczyt offsetów

Source 2.8 zachowuje generator 1.0.0 także po dodaniu known forecast plans.
Ordinary reader dopuszcza tę kombinację, nadal sprawdzając właściwą wersję,
requested/resolved parameters, pełne tabele, niezależny process replay,
reconciliation, raporty i watermarks. To rozszerzenie obsługi istniejących
parametrów, bez pomijania kontroli lub podmiany faktów.

Dwa nowe pliki `.forecast.schema.json` pochodzą z aktualnych typed modeli.
Eksporter wybiera ich komplet wyłącznie dla anomaly sources deklarujących
forecast plans. Stare pliki i zwykłe snapshoty 1.2 zachowują oryginalne bajty.
Verifier odrzuca mieszany zestaw schematów; publiczny eksport nadal nie zawiera
simulation truth. Consumer wymaga odpowiadających wariantów kontraktów.

Native kontrola obejmuje demand i physical plan na wcześniej eksponowanych
kontrolnych danych ai-smoke 30 × 8 × 3 × 2, seed42 i 14 known days: rzeczywistą
generację, ordinary writer/reader, qualification, eksport i pełny snapshot
verifier oraz JSON Schema validation. To test komponentu, nie canonical
portfolio lub projektowa kampania. Pierwszy wynik 2 failed/40 passed jest
zachowany: istniejący reader jawnie blokował łączenie anomaly i forecast plans.
Poprawiony odbiór tej kombinacji i kontrolowanego Kafka read ma 6 passed.
W pierwszej regresji zaliczono 40 kontroli starszych snapshotów i helpera
offsetów; 2 nowe kombinacje ujawniły brak obsługi przed poprawką.
Osobna regresja cohort/forecast plans ma 31 passed.

Exact source main `cbcac6eb`, CI37629010997, wykrył pojedynczy błąd Kafka
NOT_COORDINATOR przy odczycie committed offsets po restarcie własnego brokera;
742 testy API zaliczono. Porazka pozostaje zachowana. Testowy helper ponawia
wyłącznie odczyt NOT_COORDINATOR/COORDINATOR_NOT_AVAILABLE przez maksymalnie45s
w pierwotnym przyroście. Integracja source main `467f9903` zachowuje jego wspólny
helper `committed_offsets`, limit 10 s oraz dodatkowe przejściowe stany
COORDINATOR_LOAD_IN_PROGRESS/_WAIT_COORD. Sprawdza także błąd każdej zwróconej
partycji przed użyciem offsetu; błąd uprawnień pozostaje natychmiastową porażką.
Nie ponawia zapisów ani przetwarzania zdarzeń i nie tworzy domyślnych offsetów.
Wszystkie asercje trwałych bajtów, dokładnego offsetu i restartu pozostają.
Kontrole jednostkowe dowodzą realnej odpowiedzi, braku retry błędu permanentnego
oraz skończonego failure bez wymyślonego offsetu. Prawdziwy test brokera musi
ponownie przejść w pełnym CI nowego head, bez uruchamiania lokalnych kontenerów.

Nie rozpoczęto projektowej generacji AI09, nowych fitów lub final test.
AI07–08 pozostają zamknięte. Publikacja nowego source head i dokładne CI/main
oraz pełna kampania AI09 nadal są wymagane; nie przepięto istniejącego pina AI07.
