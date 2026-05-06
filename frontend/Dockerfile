FROM node:22-alpine AS build

LABEL org.opencontainers.image.title="RetailOps Frontend"
LABEL org.opencontainers.image.description="React/Vite frontend build stage for the RetailOps local runtime"
LABEL org.opencontainers.image.version="0.1.0"

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build


FROM nginx:1.27-alpine AS runtime

RUN apk add --no-cache --upgrade libcrypto3 libssl3 libxml2

LABEL org.opencontainers.image.title="RetailOps Frontend"
LABEL org.opencontainers.image.description="Nginx-served React/Vite frontend for the RetailOps local runtime"
LABEL org.opencontainers.image.version="0.1.0"

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
