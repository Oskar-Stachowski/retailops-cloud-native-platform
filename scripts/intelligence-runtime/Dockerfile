FROM python:3.11.15-slim@sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff AS build
RUN pip install --no-cache-dir uv==0.12.19
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
COPY --from=ai-owner . /ai
WORKDIR /ai/tools/intelligence-delivery
RUN uv sync --locked --no-dev --no-editable

FROM python:3.11.15-slim@sha256:90744cff8f32887f075c47d747a173ff333e9e98801667af93c357fa9f5e28ff
COPY --from=build /opt/venv /opt/venv
COPY --from=build /ai/scripts/intelligence_outbox.py /ai/intelligence_outbox.py
COPY --from=build /ai/contracts/events/v2/forecast_generated.fixture.json /ai/fixture.json
COPY ai_fixture.py /ai/ai_fixture.py
ENV PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /ai
USER 10001:10001
CMD ["python", "/ai/intelligence_outbox.py", "--broker-config", "/private/broker.json"]
