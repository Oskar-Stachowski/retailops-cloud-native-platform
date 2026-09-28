from __future__ import annotations

RETURNS_VERSION = "retail-returns-1.0.0"
CATEGORY_WINDOWS = {
    "Electronics": 14,
    "Home Improvement": 21,
    "Grocery": 3,
    "Fashion": 30,
    "Beauty": 7,
    "Sports": 21,
    "Toys": 14,
    "Pet Care": 7,
}
CHANNEL_WINDOW_OFFSETS = {"store": 0, "online": 3, "marketplace": 7, "wholesale": 0}
MAX_INGESTION_DELAY_DAYS = 2
RETURN_TAIL_DAYS = max(CATEGORY_WINDOWS.values()) + max(CHANNEL_WINDOW_OFFSETS.values())
RETURN_TAIL_DAYS += MAX_INGESTION_DELAY_DAYS
RETURN_GRAIN = ["business_date", "product_id", "selling_location_id", "channel"]
RETURN_COLUMNS = {
    "return_policies": [
        "id",
        "category_id",
        "channel",
        "window_days",
        "max_ingestion_delay_days",
        "known_at",
        "returns_policy_version",
    ],
    "return_events": [
        "id",
        "sale_id",
        "order_id",
        "order_item_id",
        "product_id",
        "selling_location_id",
        "channel",
        "policy_id",
        "quantity",
        "refund_amount",
        "currency",
        "reason",
        "status",
        "returned_at",
        "ingested_at",
        "available_at",
        "returns_policy_version",
    ],
    "daily_return_cohorts": [
        "id",
        *RETURN_GRAIN,
        "snapshot_kind",
        "as_of_time",
        "observed_units",
        "return_units",
        "net_units",
        "gross_revenue",
        "refund_amount",
        "net_revenue",
        "currency",
        "return_data_complete",
        "available_at",
        "returns_policy_version",
    ],
}
RETURN_CLASSES = {
    "return_policies": "source_plan",
    "return_events": "source_observation",
    "daily_return_cohorts": "source_observation",
}
RETURN_GRAINS = {
    "return_policies": ["category_id", "channel"],
    "return_events": ["id"],
    "daily_return_cohorts": [*RETURN_GRAIN, "as_of_time"],
}


def uses_returns(profile: str, schema_version: str = "2.5.0") -> bool:
    return profile.startswith("ai-") and schema_version in {"2.4.0", "2.5.0"}
