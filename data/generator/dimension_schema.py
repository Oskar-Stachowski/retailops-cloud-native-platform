from __future__ import annotations

DIMENSIONS_VERSION = "retail-dimensions-1.0.0"
AI_CALENDAR_VERSION = "pl-de-berlin-calendar-1.0.0"
SKU_POLICY_VERSION = "sku-1.0.0"
SKU_PATTERN = r"^[A-Z]{4}-[0-9]{6}$"
CHANNELS = ("store", "online", "marketplace", "wholesale")
CATEGORY_POLICIES = {
    "Electronics": ("ELEC", "Non-food", "Devices", 1, "pcs", (11, 12)),
    "Home Improvement": ("HOME", "Household", "Home", 1, "pcs", (3, 4, 5, 6)),
    "Grocery": ("GROC", "Food", "Everyday food", 500, "g", ()),
    "Fashion": ("FASH", "Non-food", "Clothing", 1, "pcs", (11, 12)),
    "Beauty": ("BEAU", "Non-food", "Personal care", 250, "ml", (11, 12)),
    "Sports": ("SPOR", "Non-food", "Leisure", 1, "pcs", (4, 5, 6, 7, 8)),
    "Toys": ("TOYS", "Non-food", "Leisure", 1, "pcs", (11, 12)),
    "Pet Care": ("PETC", "Household", "Pet supplies", 1000, "g", ()),
}
DIMENSION_COLUMNS = {
    "catalog_categories": [
        "id",
        "category_code",
        "name",
        "department",
        "segment",
        "seasonal_months",
    ],
    "product_catalog": [
        "id",
        "sku",
        "sku_policy_version",
        "name",
        "category_id",
        "brand",
        "launch_date",
        "discontinue_date",
        "unit_of_measure",
        "pack_quantity",
        "pack_unit",
        "unit_cost",
        "currency",
        "margin_band",
        "status",
        "available_at",
    ],
    "selling_locations": [
        "id",
        "location_code",
        "name",
        "region_code",
        "country_code",
        "city",
        "calendar_jurisdiction",
        "local_timezone",
        "business_timezone",
    ],
    "stock_locations": [
        "id",
        "location_code",
        "name",
        "region_code",
        "country_code",
        "city",
        "location_type",
    ],
    "channel_assignments": [
        "id",
        "assignment_key",
        "version",
        "legacy_store_id",
        "selling_location_id",
        "channel",
        "effective_from",
        "effective_to",
        "available_at",
    ],
    "fulfillment_routes": [
        "id",
        "route_key",
        "version",
        "selling_location_id",
        "channel",
        "stock_location_id",
        "effective_from",
        "effective_to",
        "available_at",
    ],
    "assortment": [
        "id",
        "assortment_key",
        "version",
        "product_id",
        "selling_location_id",
        "channel",
        "effective_from",
        "effective_to",
        "available_at",
    ],
    "business_calendar": [
        "id",
        "business_date",
        "selling_location_id",
        "channel",
        "assignment_id",
        "calendar_version",
        "country_code",
        "calendar_jurisdiction",
        "business_timezone",
        "local_timezone",
        "day_of_week",
        "week_of_year",
        "month",
        "quarter",
        "is_weekend",
        "is_public_holiday",
        "holiday_names",
        "is_easter",
        "is_christmas",
        "is_black_friday",
        "is_cyber_monday",
        "location_open",
        "opening_policy",
        "business_day_start_at",
        "business_day_end_at",
        "local_day_start_at",
        "local_day_end_at",
        "available_at",
    ],
    "category_calendar": [
        "id",
        "business_date",
        "category_id",
        "calendar_version",
        "is_category_season",
        "available_at",
    ],
}
DIMENSION_GRAINS = {
    "business_calendar": ["business_date", "selling_location_id", "channel"],
    "category_calendar": ["business_date", "category_id"],
}
DIMENSION_CLASSES = {
    name: "source_plan"
    if name
    in {
        "channel_assignments",
        "fulfillment_routes",
        "assortment",
        "business_calendar",
        "category_calendar",
    }
    else "source_observation"
    for name in DIMENSION_COLUMNS
}


def uses_dimensions(profile: str, schema_version: str = "2.2.0") -> bool:
    return profile.startswith("ai-") and schema_version in {"2.1.0", "2.2.0"}
