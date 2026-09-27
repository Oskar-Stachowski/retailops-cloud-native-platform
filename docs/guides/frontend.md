# Frontend

[Dokumentacja](../README.md) · [Uruchomienie lokalne](local-development.md) · [Testowanie](testing.md)

Panel operatora wykorzystuje React, React Router i Vite. Obraz kontenera buduje
aplikację i serwuje ją przez Nginx. Dane biznesowe pochodzą z API FastAPI
zasilanego PostgreSQL.

## Praca z Vite

Uruchom backend według [instrukcji lokalnej](local-development.md). Następnie:

```bash
cd frontend
npm ci
npm run dev
```

Otwórz <http://localhost:5173>. Domyślne `VITE_API_BASE_URL=/api` kieruje żądania
do proxy Vite, które przekazuje je do `http://localhost:8000` i usuwa prefiks
`/api`. W kontenerze ten sam prefiks obsługuje Nginx, przekazując żądania do
usługi `api`.

Opcjonalna konfiguracja `frontend/.env.local`:

```dotenv
VITE_API_BASE_URL=/api
```

Po zmianie tej wartości uruchom Vite ponownie. Jest to ustawienie używane przy
budowaniu aplikacji. Plik `.env` w katalogu głównym służy Compose i Make;
nie zastępuje konfiguracji Vite w `frontend/`. Jeśli zmienisz port API na hoście,
dostosuj również `server.proxy` w `frontend/vite.config.js`.

## Widoki i zachowanie

| Trasa | Zawartość |
|---|---|
| `/`, `/dashboard` | Podsumowanie biznesowe, alerty, rekomendacje i stan integracji |
| `/products` | Katalog, filtrowanie i przejście do wybranego produktu |
| `/products/:productId` | Product 360: sprzedaż, zapas, prognozy oraz obsługa workflow |
| `/forecasts` | Prognozy pobrane z API |
| `/live-operations` | Metryki zapisanych zdarzeń, świeżość strumienia i stan konsumenta |
| `/anomalies` | Sygnały z alertów dashboardu oraz ryzyka zapasu |
| `/recommendations` | Rekomendacje i dostępne dla użytkownika akcje |
| `/action-queue` | Kolejka działań operacyjnych |
| `/profile` | Tożsamość demo, uprawnienia i powiadomienia |
| `/admin` | Stan platformy z ograniczeniem dostępu według roli demo |

Akcje alertów i rekomendacji zapisują zmiany i historię workflow w bazie.
Przełącznik użytkownika jest mechanizmem demonstracyjnym. Nie zapewnia logowania
ani uwierzytelnienia produkcyjnego; zakres wyjaśnia [granica tożsamości demo](../security/demo-auth-boundary.md).

Live Operations odświeża odczyt okresowo. Konsument brokera działa jako osobny
proces; instrukcja uruchomienia jest w [przewodniku lokalnym](local-development.md#konsument-zdarzeń).

## Miejsca w kodzie

| Katalog lub plik | Odpowiedzialność |
|---|---|
| `frontend/src/router/index.jsx` | Trasy aplikacji |
| `frontend/src/pages/` | Widoki użytkownika |
| `frontend/src/components/` | Wspólne komponenty i prezentacja stanów |
| `frontend/src/services/apiClient.js` | Żądania, limity czasu i błędy HTTP |
| `frontend/src/services/retailopsApi.js` | Kontrakty biznesowe, stronicowanie i akcje workflow |
| `frontend/tests/` | Testy usług w Node |
| `frontend/e2e/` | Scenariusze Playwright |
| `frontend/nginx.conf` | Serwowanie aplikacji i proxy `/api` |

Listy i paginację opisuje [kontrakt API](../reference/api-list-contract.md).
Pełny bieżący schemat jest dostępny pod <http://localhost:8000/openapi.json>.

## Kontrola zmian

W katalogu `frontend/`:

```bash
npm test
npm run lint
npm run build
```

`npm run build` zapisuje wynik w `frontend/dist/`. `dist/`, `node_modules/` i
lokalne pliki środowiska są artefaktami lokalnymi. Zachowanie w przeglądarce
sprawdź według [instrukcji Playwright](testing.md#scenariusze-przeglądarkowe).

## Diagnostyka połączenia

Sprawdź kolejno `http://localhost:8000/health`, `http://localhost:8000/ready`
i `http://localhost:3000/api/health` dla kontenera lub
`http://localhost:5173/api/health` dla Vite. Błąd na `/ready` wskazuje problem
z dostępem do bazy; działające API i niedziałająca ścieżka `/api` wskazują
problem proxy.

Przy domyślnym `/api` przeglądarka wysyła żądania do tego samego origin co UI.
Jeśli celowo ustawisz bezpośredni adres API, jego konfiguracja CORS musi
dopuszczać origin przeglądarki. Kod błędu `not_found` pod samym
`http://localhost:8000/` jest oczekiwany: używaj `/health`, `/ready` lub `/docs`.
