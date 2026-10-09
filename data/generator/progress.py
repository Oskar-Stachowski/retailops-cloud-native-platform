"""Opt-in operational progress; never part of generated events or their identity."""

from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from functools import wraps
from time import monotonic
from typing import TYPE_CHECKING, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
    from typing import TextIO

P = ParamSpec("P")
R = TypeVar("R")
PREFIX = "RETAILOPS_PROGRESS "
_active: ContextVar[Reporter | None] = ContextVar("retailops_progress", default=None)


class Reporter:
    def __init__(self, stream: TextIO, *, interval_seconds: float = 60) -> None:
        if not 0 < interval_seconds <= 120:
            message = "source_progress_interval_must_be_within_120_seconds"
            raise ValueError(message)
        self.stream = stream
        self.interval = interval_seconds
        self.started = monotonic()
        self.sequence = 0
        self.last: dict[str, float] = {}
        self.stack: list[str] = []

    def emit(self, stage: str, event: str, **counts: object) -> None:
        now = monotonic()
        if event == "progress" and now - self.last.get(stage, float("-inf")) < self.interval:
            return
        self.sequence += 1
        self.last[stage] = now
        value = {
            "version": "source-progress-1.0.0",
            "sequence": self.sequence,
            "at_utc": datetime.now(UTC).isoformat(),
            "elapsed_seconds": now - self.started,
            "stage": stage,
            "event": event,
            "active_stages": list(self.stack),
            **counts,
        }
        self.stream.write(PREFIX + json.dumps(value, sort_keys=True, allow_nan=False) + "\n")
        self.stream.flush()


@contextmanager
def reporting(stream: TextIO, *, interval_seconds: float = 60) -> Iterator[Reporter]:
    reporter = Reporter(stream, interval_seconds=interval_seconds)
    token = _active.set(reporter)
    try:
        yield reporter
    finally:
        _active.reset(token)


def stage(name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Record entry/exit of a synchronous operation without changing its result."""

    def decorate(function: Callable[P, R]) -> Callable[P, R]:
        @wraps(function)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            reporter = _active.get()
            if reporter is None:
                return function(*args, **kwargs)
            reporter.stack.append(name)
            started = monotonic()
            try:
                reporter.emit(name, "started")
                result = function(*args, **kwargs)
                reporter.emit(name, "completed", stage_seconds=monotonic() - started)
                return result
            except BaseException as error:
                try:
                    reporter.emit(
                        name,
                        "failed",
                        error_type=type(error).__name__,
                        stage_seconds=monotonic() - started,
                    )
                except Exception:  # noqa: BLE001 - telemetry must preserve the original failure
                    error.add_note("source_progress_failure_event_unavailable")
                raise
            finally:
                reporter.stack.pop()

        return wrapped

    return decorate


def advance(
    stage: str,
    completed: int,
    *,
    unit: str,
    total: int | None = None,
    business_date: str | None = None,
    completed_business_days: int | None = None,
    total_business_days: int | None = None,
    known_queued_remaining: int | None = None,
    final: bool = False,
) -> None:
    reporter = _active.get()
    if reporter is not None:
        reporter.emit(
            stage,
            "counter_final" if final else "progress",
            completed=completed,
            total=total,
            unit=unit,
            business_date=business_date,
            completed_business_days=completed_business_days,
            total_business_days=total_business_days,
            known_queued_remaining=known_queued_remaining,
        )


def counted(name: str, values: Iterable[R], *, total: int, unit: str = "records") -> Iterator[R]:
    """Count consumed rows without prefetching, materializing, sampling or reordering."""
    if _active.get() is None:
        yield from values
        return
    completed = 0
    advance(name, completed, total=total, unit=unit)
    for value in values:
        yield value
        completed += 1
        if completed % 1024 == 0:
            advance(name, completed, total=total, unit=unit)
    advance(name, completed, total=total, unit=unit, final=True)
