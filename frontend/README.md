# RetailOps Frontend Placeholder

This is a minimal static frontend shell for the RetailOps local MVP environment.

It is intentionally simple: static HTML/CSS served by Nginx. Its purpose is to prove that the platform can run locally as a full stack with Docker Compose: frontend + API + PostgreSQL.

## Local Docker build

```bash
docker build -t retailops-frontend:local .
docker run --rm -p 3000:80 retailops-frontend:local
```

Open:

```text
http://localhost:3000
```

API health link expects the backend to be available at:

```text
http://localhost:8000/health
```
