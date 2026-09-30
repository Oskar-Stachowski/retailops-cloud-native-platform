# Multi-platform base digests are updated through reviewed dependency PRs.
FROM node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS build

LABEL org.opencontainers.image.title="RetailOps Frontend"
LABEL org.opencontainers.image.description="React/Vite frontend build stage for the RetailOps local runtime"
LABEL org.opencontainers.image.version="0.1.0"

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build


FROM nginxinc/nginx-unprivileged:1.31-alpine@sha256:26b0bf6fbf07297983cb341998d79c831508787de26627dd2a112321b9c3a4af AS runtime

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
