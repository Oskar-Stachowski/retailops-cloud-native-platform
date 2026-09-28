from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from data.generator.dimension_schema import AI_CALENDAR_VERSION, CHANNELS

# A frozen, deliberately bounded calendar policy. Extending it is a versioned change.
EASTER_DATES = {
    2024: date(2024, 3, 31),
    2025: date(2025, 4, 20),
    2026: date(2026, 4, 5),
    2027: date(2027, 3, 28),
}
OPENING_POLICY_VERSION = "synthetic-opening-1.0.0"
POLISH_HOLIDAY_SOURCE = "https://api.sejm.gov.pl/eli/acts/DU/2025/296/text.pdf"
POLISH_AMENDMENT_SOURCE = "https://dziennikustaw.gov.pl/DU/2024/1965"
BERLIN_HOLIDAY_SOURCE = "https://www.berlin.de/sen/inneres/buerger-und-staat/verfassungs-und-verwaltungsrecht/artikel.1435639.php"
BERLIN_SPECIAL_SOURCE = "https://www.berlin.de/sen/justiz/service/gesetze-und-verordnungen/2024/ausgabe-nr-28-vom-2072024-s-457-484.pdf"


def utc_midnight(day: date) -> str:
    return datetime.combine(day, time(), tzinfo=UTC).isoformat()


def day_bounds(day: date, timezone: str = "UTC") -> tuple[str, str]:
    zone = ZoneInfo(timezone)
    start = datetime.combine(day, time(), tzinfo=zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time(), tzinfo=zone).astimezone(UTC)
    return start.isoformat(), end.isoformat()


@lru_cache
def holiday_dates(year: int, jurisdiction: str) -> dict[date, str]:
    if year not in EASTER_DATES or jurisdiction not in {"PL", "DE-BE"}:
        msg = "Calendar 1.0 supports PL and DE-BE for 2024-2027 only."
        raise ValueError(msg)
    easter = EASTER_DATES[year]
    fixed = {
        (1, 1): "new_year",
        (5, 1): "labour_day",
        (12, 25): "christmas_day",
        (12, 26): "christmas_second_day",
    }
    offsets = {1: "easter_monday"}
    if jurisdiction == "PL":
        fixed.update(
            {
                (1, 6): "epiphany",
                (5, 3): "constitution_day",
                (8, 15): "assumption",
                (11, 1): "all_saints",
                (11, 11): "independence_day",
            }
        )
        offsets.update({0: "easter_sunday", 49: "pentecost", 60: "corpus_christi"})
        if year >= 2025:
            fixed[12, 24] = "christmas_eve"
    else:
        fixed.update({(3, 8): "international_womens_day", (10, 3): "german_unity"})
        offsets.update({-2: "good_friday", 39: "ascension", 50: "whit_monday"})
        if year == 2025:
            fixed[5, 8] = "liberation_day_80"
    result = {date(year, month, day): name for (month, day), name in fixed.items()}
    for offset, name in offsets.items():
        holiday = easter + timedelta(days=offset)
        result[holiday] = "|".join(sorted(filter(None, (result.get(holiday), name))))
    return result


def calendar_attributes(
    day: date, jurisdiction: str, channel: str, available_at: str
) -> dict[str, str]:
    if channel not in CHANNELS:
        msg = "Unsupported calendar channel."
        raise ValueError(msg)
    holidays = holiday_dates(day.year, jurisdiction)
    holiday = holidays.get(day, "")
    timezone = "Europe/Warsaw" if jurisdiction == "PL" else "Europe/Berlin"
    business_start, business_end = day_bounds(day)
    local_start, local_end = day_bounds(day, timezone)
    november_end = date(day.year, 11, 30)
    last_friday = november_end - timedelta(days=(november_end.weekday() - 4) % 7)
    easter = EASTER_DATES[day.year]
    is_open = True
    if channel == "store":
        is_open = day.weekday() != 6 and not holiday
    elif channel == "wholesale":
        is_open = day.weekday() < 5 and not holiday
    # Synthetic policy: no Sunday exceptions/partial hours; digital intake stays open.
    if "christmas_eve" in holiday:
        # Publication on 30 December; conservatively available from the next UTC day.
        available_at = max(available_at, "2024-12-31T00:00:00+00:00")
    if "liberation_day_80" in holiday:
        available_at = max(available_at, "2024-07-21T00:00:00+00:00")
    return {
        "calendar_version": AI_CALENDAR_VERSION,
        "country_code": jurisdiction[:2],
        "calendar_jurisdiction": jurisdiction,
        "business_timezone": "UTC",
        "local_timezone": timezone,
        "day_of_week": str(day.isoweekday()),
        "week_of_year": str(day.isocalendar().week),
        "month": str(day.month),
        "quarter": str((day.month - 1) // 3 + 1),
        "is_weekend": str(day.weekday() >= 5).lower(),
        "is_public_holiday": str(bool(holiday)).lower(),
        "holiday_names": holiday,
        "is_easter": str(day == easter).lower(),
        "is_christmas": str(day.month == 12 and day.day in {24, 25, 26}).lower(),
        "is_black_friday": str(day == last_friday).lower(),
        "is_cyber_monday": str(day == last_friday + timedelta(days=3)).lower(),
        "location_open": str(bool(is_open)).lower(),
        "opening_policy": OPENING_POLICY_VERSION,
        "business_day_start_at": business_start,
        "business_day_end_at": business_end,
        "local_day_start_at": local_start,
        "local_day_end_at": local_end,
        "available_at": available_at,
    }
