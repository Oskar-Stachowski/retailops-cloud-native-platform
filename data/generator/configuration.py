from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from data.generator.common import BASE_DATE

CONFIG_VERSION = "1.0.0"
CALENDAR_VERSION = "legacy-weekday-seasonality-1.0.0"
AI_END_DATE = date(2026, 7, 31)
FORECAST_PLAN_VERSION = "known-forecast-plans-1.0.0"


@dataclass(frozen=True)
class SyntheticProfileDefaults:
    days: int
    products: int
    stores: int
    warehouses: int


PROFILE_DEFAULTS = {
    "small": SyntheticProfileDefaults(90, 100, 5, 3),
    "medium": SyntheticProfileDefaults(180, 500, 20, 6),
    "large": SyntheticProfileDefaults(365, 1000, 50, 10),
    "ai-smoke": SyntheticProfileDefaults(30, 20, 3, 2),
    "ai-temporal-smoke": SyntheticProfileDefaults(102, 8, 3, 2),
    "ai-dev": SyntheticProfileDefaults(365, 100, 5, 3),
    "ai-intermittent-v1": SyntheticProfileDefaults(365, 100, 5, 3),
    "ai-stockout-stress-v1": SyntheticProfileDefaults(102, 30, 3, 2),
    "ai-training": SyntheticProfileDefaults(730, 200, 10, 4),
    "ai-07-portfolio-v1": SyntheticProfileDefaults(128, 8, 3, 2),
    "ai-07-portfolio-v2": SyntheticProfileDefaults(128, 8, 2, 2),
    "ai-07-portfolio-v3": SyntheticProfileDefaults(128, 12, 2, 2),
    "ai-07-portfolio-v4": SyntheticProfileDefaults(128, 12, 2, 2),
}
SUPPORTED_PROFILES = ("demo", *PROFILE_DEFAULTS, "ai-load")
SIZING_FIELDS = ("days", "products", "stores", "warehouses")


@dataclass(frozen=True)
class DatasetGenerationConfig:
    profile: str = "demo"
    days: int | None = None
    products: int | None = None
    stores: int | None = None
    warehouses: int | None = None
    seed: int = 42
    start_date: date | None = None
    end_date: date | None = None
    max_daily_rows: int | None = None
    forecast_plan_days: int = 0


@dataclass(frozen=True)
class ResolvedGenerationConfig:
    profile: str
    days: int
    products: int
    stores: int
    warehouses: int
    seed: int
    start_date: date
    end_date: date
    max_daily_rows: int
    business_timezone: str = "UTC"
    output_format: str = "csv"
    warmup_days: int = 0
    origin_days: int = 0
    label_tail_days: int = 0
    forecast_plan_days: int = 0

    @property
    def planning_end_date(self) -> date:
        return self.end_date + timedelta(days=self.forecast_plan_days)

    @property
    def planning_days(self) -> int:
        return self.days + self.forecast_plan_days

    def parameters(self) -> dict[str, Any]:
        result = asdict(self)
        result["start_date"] = self.start_date.isoformat()
        result["end_date"] = self.end_date.isoformat()
        if self.forecast_plan_days:
            result["forecast_plan_version"] = FORECAST_PLAN_VERSION
        else:
            result.pop("forecast_plan_days")
        return result


def requested_parameters(config: DatasetGenerationConfig) -> dict[str, Any]:
    result = asdict(config)
    for key in ("start_date", "end_date"):
        result[key] = result[key].isoformat() if result[key] is not None else None
    if config.forecast_plan_days:
        result["forecast_plan_version"] = FORECAST_PLAN_VERSION
    else:
        result.pop("forecast_plan_days")
    return result


def validate_generation_config(config: DatasetGenerationConfig) -> None:
    if config.profile not in SUPPORTED_PROFILES:
        msg = f"Unsupported dataset profile '{config.profile}'."
        raise ValueError(msg)
    if (
        type(config.forecast_plan_days) is not int
        or not 0 <= config.forecast_plan_days <= 14
        or (config.forecast_plan_days and not config.profile.startswith("ai-"))
    ):
        msg = "Forecast plans require an AI profile and an integer horizon of 0-14 days."
        raise ValueError(msg)
    for name in (*SIZING_FIELDS, "seed", "max_daily_rows"):
        value = getattr(config, name)
        if (name == "seed" or value is not None) and (type(value) is not int or value <= 0):
            msg = f"Dataset generation options must be positive integers: {name}."
            raise ValueError(msg)
    for name in ("start_date", "end_date"):
        value = getattr(config, name)
        if value is not None and type(value) is not date:
            msg = f"Dataset generation option must be an ISO date: {name}."
            raise ValueError(msg)
    if config.start_date and config.end_date and config.start_date > config.end_date:
        msg = "start_date must not be after end_date."
        raise ValueError(msg)
    if config.profile == "ai-stockout-stress-v1" and config.end_date is None:
        msg = "Stockout stress requires an explicit prospective end date."
        raise ValueError(msg)


def resolve_generation_config(config: DatasetGenerationConfig) -> ResolvedGenerationConfig:
    validate_generation_config(config)
    if config.profile == "demo":
        # The fixed scenario has four sale dates; CLI sizing and seed are ignored.
        start = BASE_DATE - timedelta(days=3)
        if config.start_date not in (None, start) or config.end_date not in (None, BASE_DATE):
            msg = "Demo dates are fixed; use a scalable profile for date overrides."
            raise ValueError(msg)
        return ResolvedGenerationConfig("demo", 4, 8, 4, 4, 42, start, BASE_DATE, 128)

    if config.profile == "ai-load":
        if any(getattr(config, key) is None for key in (*SIZING_FIELDS, "max_daily_rows")):
            msg = "ai-load requires explicit days, products, stores, warehouses and max_daily_rows."
            raise ValueError(msg)
        defaults = SyntheticProfileDefaults(
            config.days, config.products, config.stores, config.warehouses
        )
    else:
        defaults = PROFILE_DEFAULTS[config.profile]
    values = {key: getattr(config, key) or getattr(defaults, key) for key in SIZING_FIELDS}
    if config.start_date and config.end_date:
        days = (config.end_date - config.start_date).days + 1
        if config.days is not None and config.days != days:
            msg = "days must equal the inclusive start_date/end_date interval."
            raise ValueError(msg)
        values["days"] = days
    end = config.end_date or (
        date(2025, 5, 8)
        if config.profile == "ai-07-portfolio-v4"
        else date(2026, 5, 8)
        if config.profile == "ai-07-portfolio-v3"
        else AI_END_DATE
        if config.profile.startswith("ai-")
        else BASE_DATE
    )
    if config.start_date:
        end = config.end_date or config.start_date + timedelta(days=values["days"] - 1)
    start = end - timedelta(days=values["days"] - 1)
    if config.profile == "ai-stockout-stress-v1" and values["days"] < 84:
        msg = "Stockout stress requires at least 84 days including controls and tail."
        raise ValueError(msg)
    daily_rows = values["days"] * values["products"] * values["stores"]
    limit = config.max_daily_rows or daily_rows
    if daily_rows > limit:
        msg = "Declared daily grid exceeds max_daily_rows; generation was not started."
        raise ValueError(msg)
    layout: dict[str, int] = {}
    if config.profile == "ai-temporal-smoke":
        if values["days"] < 43:
            msg = "ai-temporal-smoke requires 28 warmup, at least one origin and 14 tail days."
            raise ValueError(msg)
        layout = {"warmup_days": 28, "origin_days": values["days"] - 42, "label_tail_days": 14}
    return ResolvedGenerationConfig(
        profile=config.profile,
        seed=config.seed,
        start_date=start,
        end_date=end,
        max_daily_rows=limit,
        forecast_plan_days=config.forecast_plan_days,
        **values,
        **layout,
    )
