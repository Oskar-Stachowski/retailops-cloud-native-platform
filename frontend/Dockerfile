# Tag pinning is intentional for local and portfolio reproducibility.
# Production deployment manifests should prefer digest-pinned base images.
FROM node:22-alpine AS build

LABEL org.opencontainers.image.title="RetailOps Frontend"
LABEL org.opencontainers.image.description="React/Vite frontend build stage for the RetailOps local runtime"
LABEL org.opencontainers.image.version="0.1.0"

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build


FROM nginxinc/nginx-unprivileged:1.29-alpine AS runtime

LABEL org.opencontainers.image.title="RetailOps Frontend"
LABEL org.opencontainers.image.description="Nginx-served React/Vite frontend for the RetailOps local runtime"
LABEL org.opencontainers.image.version="0.1.0"

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build --chown=101:101 /app/dist /usr/share/nginx/html

USER 101:101

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1:8080/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
