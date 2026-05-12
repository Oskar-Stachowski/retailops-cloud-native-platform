FROM python:3.11-slim

LABEL org.opencontainers.image.title="RetailOps API"
LABEL org.opencontainers.image.description="FastAPI backend for the RetailOps local runtime"
LABEL org.opencontainers.image.version="0.1.0"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV APP_HOME=/app

WORKDIR ${APP_HOME}

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

RUN adduser --disabled-password --gecos "" appuser

COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser alembic.ini .
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser scripts ./scripts

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD curl --fail --silent --show-error http://localhost:8000/ready || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
