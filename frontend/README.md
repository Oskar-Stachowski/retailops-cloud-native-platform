# RetailOps Frontend

React + Vite user-facing shell for the RetailOps dashboard platform.

This frontend is the first browser-facing layer of the RetailOps MVP. It introduces the dashboard layout, planned modules, local environment status, and a live API health card connected to the FastAPI backend.

## Purpose

The frontend validates that RetailOps can run as a local full-stack application:

- React/Vite dashboard shell
- FastAPI health contract integration
- PostgreSQL service prepared through Docker Compose
- Nginx-based production container for serving the built frontend
- `/api/health` proxy from the frontend to the backend

This task does not yet implement full business dashboards. It prepares the UI foundation for future modules such as inventory risk, alerts, forecasting, anomaly detection, product 360, and platform health.

## Tech stack

| Area | Technology | Purpose |
| --- | --- | --- |
| UI framework | React | Component-based frontend development |
| Build tool | Vite | Fast local development and production build |
| Language | JavaScript | MVP frontend implementation |
| Styling | CSS | Dashboard shell layout and visual system |
| Static serving | Nginx | Serves the production `dist/` build in Docker |
| Local integration | Docker Compose | Runs frontend, API, and database together |

## Project structure

```text
frontend/
├── public/                 # Static public assets
├── src/
│   ├── data/               # JSON-driven dashboard content
│   │   ├── modules.json
│   │   └── stack.json
│   ├── App.css             # Main dashboard styling
│   ├── App.jsx             # Main React application shell
│   └── main.jsx            # React entrypoint
├── Dockerfile              # Multi-stage React/Vite build served by Nginx
├── nginx.conf              # Nginx routing and API proxy configuration
├── package.json            # Frontend scripts and dependencies
├── package-lock.json       # Locked npm dependency versions
├── vite.config.js          # Vite config and development proxy
└── README.md
```

## Local development

Run the frontend in development mode:

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

The Vite development server proxies API requests from:

```text
/api/health
```

to the local backend:

```text
http://localhost:8000/health
```

## API health integration

The dashboard includes a live API health card. It calls:

```text
/api/health
```

Expected backend response:

```json
{
  "status": "ok",
  "service": "retailops-api",
  "environment": "local"
}
```

In development mode, Vite handles the proxy. In Docker Compose, Nginx handles the proxy to the internal `api` service.

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

Open:

```text
http://localhost:3000
```

The browser calls the frontend container. Nginx proxies `/api/health` to the backend service inside the Docker Compose network:

```text
Browser → Frontend/Nginx → /api/health → api:8000/health → FastAPI
```

## Useful commands

```bash
# Install dependencies
npm install

# Start local Vite dev server
npm run dev

# Build production assets
npm run build

# Run linting, if configured in package.json
npm run lint

# Build Docker image
docker build -t retailops-frontend:local .
```

## Ports

| Service | Local URL | Notes |
| --- | --- | --- |
| Vite dev server | `http://localhost:5173` | Used during frontend development |
| Frontend container | `http://localhost:3000` | Served by Nginx through Docker Compose |
| API backend | `http://localhost:8000/health` | FastAPI health endpoint |

## Troubleshooting

### `/api/health` does not work in Vite

Check that the backend is running:

```bash
curl http://localhost:8000/health
```

Then restart Vite after changing `vite.config.js`:

```bash
npm run dev
```

### Nginx says `host not found in upstream "api"`

This usually happens when the frontend container is started alone with `docker run`.

The `api` hostname exists inside the Docker Compose network, so run the full stack instead:

```bash
docker compose up --build
```

### `node_modules` or `dist` appears in Git status

Make sure `.gitignore` contains:

```gitignore
node_modules
dist
.env
.env.local
```

