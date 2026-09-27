# Użytkownicy i procesy operacyjne

[Dokumentacja](../README.md) · [Frontend](../guides/frontend.md) · [API](api.md)

Operator zaczyna od dashboardu i kolejki działań, otwiera Product 360, ocenia
sprzedaż, zapas oraz sygnały i podejmuje decyzję dotyczącą alertu lub rekomendacji.
Zmiany stanu i historia są zapisywane w PostgreSQL.

## Role demonstracyjne

| Użytkownik demo | Rola w scenariuszu | Zakres uprawnień zadeklarowany w aplikacji |
|---|---|---|
| `platform-admin` | Administracja platformą | Wszystkie uprawnienia demo |
| `ops-manager` | Obsługa operacyjna | Odczyty biznesowe, workflow i powiadomienia |
| `inventory-planner` | Planowanie zapasu | Odczyty biznesowe, workflow i powiadomienia |
| `commercial-analyst` | Analiza handlowa | Dashboard, produkty, prognozy i powiadomienia |
| `read-only-viewer` | Przegląd wyników | Dashboard i produkty, bez mutacji workflow |

Źródłem definicji jest [roles.py](../../services/api/app/auth/roles.py). UI i
wybrane endpointy sprawdzają te uprawnienia. Nie jest to kompletna kontrola
dostępu do wszystkich odczytów API ani system logowania: klient wybiera
`user_id`, a domyślny użytkownik to administrator demo. Zobacz
[ograniczenia tożsamości](../security/demo-auth-boundary.md).

## Obsługa alertu

| Operacja API | Dozwolony stan początkowy | Wynik |
|---|---|---|
| `acknowledge` | `open` | `acknowledged` |
| `assign` | `open`, `acknowledged`, `in_progress` | `in_progress`, przypisanie do UUID użytkownika bazy |
| `resolve` | `acknowledged`, `in_progress` | `resolved` |
| `dismiss` | `open`, `acknowledged`, `in_progress` | `dismissed`, wymagany komentarz decyzji |
| `comment` | Bieżący stan | Zapis historii bez zmiany stanu |

Ścieżka to `POST /alerts/{alert_id}/{operacja}`. Rozwiązanie otwartego alertu
wymaga najpierw potwierdzenia albo przypisania. Dzięki temu zapis rozróżnia
zauważenie problemu od zakończenia jego obsługi.

## Obsługa rekomendacji

| Operacja API | Dozwolony stan początkowy | Wynik |
|---|---|---|
| `accept` | `proposed` | `accepted` |
| `assign` | `proposed`, `accepted` | Stan bez zmian; przypisanie zapisane w historii audytowej |
| `resolve` | `accepted` | `implemented` |
| `reject`, `dismiss` | `proposed` | `rejected`, wymagany komentarz decyzji |

Ścieżka to `POST /recommendations/{recommendation_id}/{operacja}`. Akceptacja
oznacza decyzję o realizacji, a dopiero `resolve` potwierdza wykonanie. Obecna
tabela rekomendacji nie ma kolumny właściciela; przypisanie jest informacją
w `workflow_audit_log`.

Publiczne routery nie udostępniają ponownego otwarcia, eskalacji ani komentarza
do rekomendacji. Same wartości obecne w domenowych enumach nie oznaczają
istnienia endpointu lub przycisku w UI.

## Komentarze, historia i ponawianie

Mutacje wymagają uprawnienia `workflow:write`. Przy `assign` podaj
`assigned_to_user_id` jako UUID z tabeli `users`; tekstowy identyfikator
demonstracyjny, np. `ops-manager`, nie jest UUID przypisania. Podany komentarz
powinien mieć 5–1000 znaków. Odrzucenie lub pominięcie bez uzasadnienia zostaje
odrzucone.

Opcjonalny `idempotency_key` ma 8–120 znaków. Ponowienie tej samej operacji na
tym samym zasobie z tym kluczem odczytuje wcześniejszy zapis audytowy. Nowa
decyzja wymaga nowego klucza; użycie poprzedniego klucza dla innego typu akcji
powoduje konflikt. Jest to mechanizm ponowień pojedynczej mutacji, nie
koordynacja całego procesu biznesowego.

Historia zapisuje stan przed i po zmianie, wykonawcę, czas, komentarz i klucz
idempotencji. Użytkownik demo jest mapowany na rekord bazy według loginu, potem
roli, a w ostateczności dostępnego aktywnego użytkownika. Dlatego ta historia
obrazuje lokalny przebieg procesu, nie dowodzi tożsamości uwierzytelnionego
człowieka.

Implementacja: [routery alertów](../../services/api/app/api/alerts.py),
[routery rekomendacji](../../services/api/app/api/recommendations.py),
[reguły przejść](../../services/api/app/domain/workflow.py),
[serwis](../../services/api/app/services/workflow_service.py) i
[repozytorium](../../services/api/app/repositories/workflow_repository.py).

Powiadomienia w profilu są oddzielną demonstracją. Oznaczenie ich jako
przeczytanych zmienia pamięć procesu API i nie jest trwałym zamknięciem alertu.
