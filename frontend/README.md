# RetailOps Frontend

React + Vite user-facing dashboard for the RetailOps Cloud-Native AI Platform.

The frontend is the browser-facing layer of the RetailOps MVP. After **CS-016 — Connect dashboard UI to backend APIs**, the key dashboard views no longer rely on local mock business records. They load live data from the FastAPI backend and display real seeded retail data from the local PostgreSQL-backed API.

## Purpose

The frontend validates that RetailOps can run as a local full-stack application:

- React/Vite dashboard UI
- FastAPI backend integration through `VITE_API_BASE_URL`
- live API health and readiness checks
- product catalogue data from `/products`
- demand forecast data from `/forecasts`
- stock risk signals from `/inventory-risks`
- dashboard summary data from `/dashboard/summary`
- Docker Compose local runtime with frontend, API, and database

This frontend is still an MVP interface. It proves API integration, routing, local runtime, and dashboard evidence. Advanced UX, authentication, RBAC, workflow actions, charts, filtering, and production observability views are intentionally left for later tasks.

## Sprint 5 — Dashboard and Operations View MVP

Sprint 5 extends the frontend dashboard from a basic API integration view into a business-facing operational dashboard.

The dashboard now consumes these backend endpoints when available:

- `GET /dashboard/summary`
- `GET /dashboard/operational-visibility`
- `GET /dashboard/sales-trend`
- `GET /dashboard/alerts`
- `GET /dashboard/recommendations`
- `GET /dashboard/open-work-items`
- `GET /dashboard/stock-risk-summary`
- `GET /products`
- `GET /forecasts`
- `GET /inventory-risks`
- `GET /health`
- `GET /ready`

The implementation stays read-only and local-first. It does not introduce authentication, workflow mutations, charting dependencies or cloud infrastructure.

## Sprint 6 — Product 360 and Operational Workflow MVP

Sprint 6 introduces a Product 360 read-only drill-down view.

The frontend Products page now links to a product-level view backed by:

- `GET /products/{product_id}/360`

The Product 360 endpoint aggregates product metadata, sales, inventory snapshots, forecasts, anomalies, alerts, recommendations, workflow actions and stock-risk context.

The implementation is intentionally read-only. Workflow mutations such as approve, reject, assign, comment and escalation remain future scope.

## Sprint 7 — Users, Roles and Notifications

Sprint 7 adds the first DevOps-facing access and operational-awareness layer to RetailOps.

The implementation is intentionally local-first and mock-auth only. It introduces selectable demo users, role-aware frontend boundaries, current-user API contracts and in-app notifications without adding production authentication or external identity providers.

New backend endpoints:

- `GET /users/demo`
- `GET /me`
- `GET /me/permissions`
- `GET /notifications`
- `POST /notifications/{notification_id}/read`

Frontend additions:

- demo user switcher in the top navigation,
- notification badge,
- `/profile` page with current user, permissions and notifications,
- role-aware Admin access boundary,
- frontend service tests for user-scoped API calls.

Current scope boundary:

- no real login,
- no JWT/OIDC/SSO,
- no persistent notification state,
- no database-backed users,
- no workflow approval/rejection mutations yet.

This sprint prepares the platform for future production-grade authentication, RBAC, audit logs and operational workflow write APIs.

## Tech stack

| Area | Technology | Purpose |
| --- | --- | --- |
| UI framework | React | Component-based frontend development |
| Build tool | Vite | Fast local development and production build |
| Routing | React Router | Client-side navigation between dashboard pages |
| Language | JavaScript | MVP frontend implementation |
| Styling | CSS | Dashboard shell, API-connected pages, status cards, and tables |
| API client | Fetch API | Calls FastAPI endpoints from the browser |
| Runtime config | Vite env variables | Uses `VITE_API_BASE_URL` for backend base URL |
| Static serving | Nginx | Serves the production `dist/` build in Docker |
| Local integration | Docker Compose | Runs frontend, API, and database together |

## Project structure

```text
frontend/
├── public/                    # Static public assets
├── src/
│   ├── assets/                # Frontend images and static assets
│   ├── components/            # Reusable UI components
│   │   ├── DataTable.jsx
│   │   ├── EndpointStatusCard.jsx
│   │   ├── ErrorState.jsx
│   │   ├── LoadingState.jsx
│   │   ├── MetricCard.jsx
│   │   ├── StatusBadge.jsx
│   │   └── Topbar.jsx
│   ├── pages/                 # Route-level pages
│   │   ├── Admin.jsx
│   │   ├── Anomalies.jsx
│   │   ├── Dashboard.jsx
│   │   ├── Forecasts.jsx
│   │   ├── Products.jsx
│   │   └── Recommendations.jsx
│   ├── router/                # React Router configuration
│   │   └── index.jsx
│   ├── services/              # API client and backend integration helpers
│   │   ├── apiClient.js
│   │   └── retailopsApi.js
│   ├── styles/                # Shared CSS for API-connected views
│   │   └── api-connected-ui.css
│   ├── App.css                # Main app shell styling
│   ├── App.jsx                # Root application layout
│   ├── index.css              # Global styles
│   └── main.jsx               # React entrypoint
├── tests/                     # Node test runner tests for API helpers
│   └── apiClient.test.js
├── Dockerfile                 # Multi-stage React/Vite build served by Nginx
├── eslint.config.js           # ESLint configuration
├── nginx.conf                 # Nginx routing for production container
├── package.json               # Frontend scripts and dependencies
├── package-lock.json          # Locked npm dependency versions
├── vite.config.js             # Vite configuration
└── README.md
```

## Runtime configuration

Create a local frontend environment file:

```bash
cd frontend
touch .env.local
```

Recommended local value:

```env
VITE_API_BASE_URL=http://localhost:8000
```

This value tells the browser where the FastAPI backend is available.

Important notes:

- `VITE_API_BASE_URL` must point to the backend address visible from the browser.
- In local Vite development, this is usually `http://localhost:8000`.
- In Docker Compose browser testing, this can also be `http://localhost:8000` because the backend port is published to the host.
- Restart Vite after changing `.env.local`.
- Do not commit `.env.local`.

A safe `.env.example` entry is:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Local development

Start the backend stack first from the repository root:

```bash
docker compose up --build
```

In a second terminal, start the frontend development server:

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

The frontend should call the backend at:

```text
http://localhost:8000
```

Useful backend checks:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl http://localhost:8000/products
curl http://localhost:8000/forecasts
curl http://localhost:8000/dashboard/summary
curl http://localhost:8000/inventory-risks
```

`http://localhost:8000/` may return a standardized `not_found` response. That is expected because the API root endpoint is not part of the current contract.

## Application routes

The frontend uses React Router to expose the MVP dashboard routes.

| Route | Page | Current behavior |
| --- | --- | --- |
| `/` | Dashboard | Loads live backend summary, product, forecast, health, readiness, and inventory-risk data |
| `/products` | Products | Loads product catalogue records from `/products` |
| `/forecasts` | Forecasts | Loads demand forecast records from `/forecasts` |
| `/anomalies` | Anomalies | Shows CS-016 scope boundary until a backend `/anomalies` endpoint exists |
| `/recommendations` | Recommendations | Shows CS-016 scope boundary until recommendation/workflow endpoints exist |
| `/admin` | Admin | Loads platform health and readiness from `/health` and `/ready` |

## Backend endpoints used by the frontend

| Endpoint | Used by | Purpose |
| --- | --- | --- |
| `/health` | Dashboard, Admin | Confirms API process is reachable |
| `/ready` | Dashboard, Admin | Confirms API and database readiness |
| `/dashboard/summary` | Dashboard | Provides dashboard-level metrics when available |
| `/products` | Dashboard, Products | Provides product catalogue records |
| `/forecasts` | Dashboard, Forecasts | Provides demand forecast records |
| `/inventory-risks` | Dashboard | Provides stockout, overstock, normal, or unknown inventory risk signals |

## API response shape assumptions

List endpoints may return either a direct array or an object with an `items` key.

Supported examples:

```json
[
  {
    "sku": "ELEC-HEAD-001",
    "name": "Wireless Headphones"
  }
]
```

```json
{
  "items": [
    {
      "sku": "ELEC-HEAD-001",
      "name": "Wireless Headphones"
    }
  ],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 8
  }
}
```

Forecast records currently use backend fields such as:

```json
{
  "product_id": "85710dbe-1aea-50ac-a155-fb216e12ab97",
  "forecast_period_start": "2026-05-01",
  "forecast_period_end": "2026-05-07",
  "predicted_quantity": 69.0,
  "unit_of_measure": "pcs",
  "generated_at": "2026-04-30T06:00:00Z",
  "method": "retailops-baseline-demand-model",
  "confidence_level": 0.68
}
```

The frontend maps these fields into table-friendly labels such as period, predicted quantity, confidence, method, and generated date.

## CORS and browser integration

Because the Vite dev server usually runs on `http://localhost:5173` and FastAPI runs on `http://localhost:8000`, the browser treats them as different origins.

The backend must allow the local frontend origins through CORS, for example:

```text
http://localhost:5173
http://127.0.0.1:5173
http://localhost:3000
http://127.0.0.1:3000
```

`curl` can succeed even when the browser fails, because CORS is enforced by browsers, not by `curl`.

## Production build

Build the frontend production artifact:

```bash
cd frontend
npm run build
```

Expected output:

```text
dist/
├── index.html
└── assets/
```

The `dist/` directory is a build artifact and should not be committed to Git.

## Docker build

Build the frontend image:

```bash
cd frontend
docker build -t retailops-frontend:local .
```

The Dockerfile uses a multi-stage build:

1. Node builds the React/Vite application.
2. Nginx serves the generated `dist/` files.

## Docker Compose usage

From the repository root, run the full local stack:

```bash
docker compose up --build
```

Expected local services:

| Service | Local URL | Notes |
| --- | --- | --- |
| Vite dev server | `http://localhost:5173` | Used during active frontend development |
| Frontend container | `http://localhost:3000` | Served by Nginx through Docker Compose |
| API backend | `http://localhost:8000` | FastAPI backend |
| PostgreSQL | `localhost:5432` | Local database container |

For CS-016 browser validation, the most useful path is:

```text
Browser → Vite frontend on localhost:5173 → FastAPI on localhost:8000 → PostgreSQL
```

When testing the containerized frontend:

```text
Browser → Frontend container on localhost:3000 → FastAPI on localhost:8000 → PostgreSQL
```

## Quality checks

Run the minimum frontend checks before committing:

```bash
cd frontend
npm test
npm run lint
npm run build
```

What these checks cover:

| Command | Purpose |
| --- | --- |
| `npm test` | Tests API client helpers and response normalization |
| `npm run lint` | Checks JavaScript/React style and hook usage |
| `npm run build` | Verifies that the production frontend build succeeds |

These checks do not fully replace browser smoke testing. After CS-016, also verify the app manually in the browser.

## Useful commands

```bash
# Install dependencies
npm install

# Start local Vite dev server
npm run dev

# Run frontend tests
npm test

# Run linting
npm run lint

# Build production assets
npm run build

# Build Docker image
docker build -t retailops-frontend:local .
```

Backend smoke commands:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl http://localhost:8000/products
curl http://localhost:8000/forecasts
curl http://localhost:8000/dashboard/summary
curl http://localhost:8000/inventory-risks
```

## Troubleshooting

### Frontend shows `Backend API is not reachable`

Check that the backend is running:

```bash
curl http://localhost:8000/health
```

If this fails, start or rebuild the local stack:

```bash
docker compose up --build
```

### `curl` works but the browser shows unavailable

This is usually a CORS or frontend base URL problem.

Check `.env.local`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

Then restart Vite:

```bash
npm run dev
```

Open DevTools → Network and confirm requests are going to:

```text
http://localhost:8000/health
```

If requests are going to `http://localhost:5173/health`, Vite did not pick up the backend base URL.

### Browser console shows a CORS error

Make sure the FastAPI backend allows local frontend origins, especially:

```text
http://localhost:5173
http://localhost:3000
```

After changing backend CORS settings, rebuild or restart the API container:

```bash
docker compose down
docker compose up --build
```

### `localhost:8000` shows `not_found`

This is expected. The API root path `/` is not part of the current contract.

Use explicit endpoints instead:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

### Forecast table shows dashes

The frontend and backend field names may be out of sync.

Check the backend response:

```bash
curl http://localhost:8000/forecasts
```

The frontend expects fields such as:

```text
product_id
forecast_period_start
forecast_period_end
predicted_quantity
unit_of_measure
confidence_level
method
generated_at
```

### `node_modules` or `dist` appears in Git status

Make sure `.gitignore` contains:

```gitignore
node_modules
dist
.env
.env.local
```
