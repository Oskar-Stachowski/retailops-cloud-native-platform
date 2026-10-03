"""Dedicated v2 processor plugs into the existing serial, fail-stop manual-ACK runner."""

from __future__ import annotations

from typing import Any

from app.repositories.intelligence_repository import IntelligenceRepository
from app.services.intelligence_contract import validate_event


class IntelligenceEventConsumer:
    def __init__(self, repository: IntelligenceRepository | None = None) -> None:
        self.repository = repository or IntelligenceRepository()

    def process_event(
        self,
        event: dict[str, Any],
        *,
        transport_topic: str | None = None,
    ) -> dict[str, Any]:
        validate_event(event, transport_topic=transport_topic)
        return self.repository.project(event)

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def record_quarantined(self, *, decoded: bool, error: str) -> None:
        # Exact bytes/transport position have already committed in the shared quarantine.
        pass
