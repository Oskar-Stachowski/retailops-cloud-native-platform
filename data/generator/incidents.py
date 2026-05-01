from __future__ import annotations

from data.generator.common import deterministic_uuid, money
from data.generator.common import utc_datetime
from data.generator.products import product_by_sku
from data.generator.users import user_by_role

INCIDENT_SCENARIOS: list[dict[str, object]] = [
    {
        "sku": "DAIRY-MILK-001",
        "anomaly_type": "sales_drop",
        "alert_type": "sales_drop",
        "rationale": "sales_drop",
        "severity": "high",
        "metric_name": "units_sold",
        "impact_unit": "l",
        "actual_value": 42,
        "expected_value": 130,
        "recommendation_type": "investigate_sales_drop",
        "recommendation_status": "proposed",
        "workflow_status": "open",
        "action_type": "acknowledge",
        "actor_role": "category_manager",
        "comment": "Initial review started.",
    },
    {
        "sku": "HOME-FLOOR-001",
        "anomaly_type": "stale_inventory",
        "alert_type": "stale_inventory",
        "rationale": "stale_inventory",
        "severity": "medium",
        "metric_name": "days_of_supply",
        "impact_unit": "days",
        "actual_value": 126,
        "expected_value": 30,
        "recommendation_type": "refresh_inventory_data",
        "recommendation_status": "accepted",
        "workflow_status": "acknowledged",
        "action_type": "assign",
        "actor_role": "admin",
        "comment": "Assigned to inventory planning team.",
    },
    {
        "sku": "ELEC-HEAD-001",
        "anomaly_type": "sales_drop",
        "alert_type": "sales_drop",
        "rationale": "sales_drop",
        "severity": "medium",
        "metric_name": "units_sold",
        "impact_unit": "pcs",
        "actual_value": 5,
        "expected_value": 18,
        "recommendation_type": "review_price",
        "recommendation_status": "proposed",
        "workflow_status": "acknowledged",
        "action_type": "comment",
        "actor_role": "analyst",
        "comment": "Marketplace price comparison is being prepared.",
    },
    {
        "sku": "FASHION-JACKET-001",
        "anomaly_type": "sales_spike",
        "alert_type": "stockout_risk",
        "rationale": "stockout_risk",
        "severity": "critical",
        "metric_name": "on_hand_quantity",
        "impact_unit": "pcs",
        "actual_value": 9,
        "expected_value": 48,
        "recommendation_type": "replenish_stock",
        "recommendation_status": "proposed",
        "workflow_status": "open",
        "action_type": "accept",
        "actor_role": "inventory_planner",
        "comment": "Replenishment recommendation accepted.",
    },
]


def _deviation_percentage(actual_value: float, expected_value: float) -> str:
    deviation = ((actual_value - expected_value) / expected_value) * 100
    return money(deviation)


def _alert_status(product_sku: str) -> str:
    if product_sku == "ELEC-HEAD-001":
        return "in_progress"

    if product_sku == "HOME-FLOOR-001":
        return "acknowledged"

    return "open"


def _assigned_to_user_id(
    users: list[dict[str, str]],
    alert_type: str,
) -> str:
    role_by_alert_type = {
        "sales_drop": "category_manager",
        "sales_spike": "category_manager",
        "stale_inventory": "inventory_planner",
        "stockout_risk": "inventory_planner",
    }

    assigned_role = role_by_alert_type.get(alert_type, "analyst")

    return user_by_role(users, assigned_role)["id"]


def generate_incident_dataset(
    products: list[dict[str, str]],
    forecasts: list[dict[str, str]],
    users: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    anomalies: list[dict[str, str]] = []
    alerts: list[dict[str, str]] = []
    recommendations: list[dict[str, str]] = []
    workflow_actions: list[dict[str, str]] = []

    for index, scenario in enumerate(INCIDENT_SCENARIOS):
        product = product_by_sku(products, str(scenario["sku"]))
        # forecast = forecast_by_product_id(forecasts, product["id"])
        actor = user_by_role(users, str(scenario["actor_role"]))

        anomaly_id = deterministic_uuid("anomaly", product["sku"])
        alert_id = deterministic_uuid("alert", product["sku"])
        recommendation_id = deterministic_uuid(
            "recommendation",
            product["sku"],
        )
        workflow_action_id = deterministic_uuid(
            "workflow_action",
            product["sku"],
        )
        actual_value = float(scenario["actual_value"])
        expected_value = float(scenario["expected_value"])
        recommendation_status = scenario["recommendation_status"]

        recommendation_date = utc_datetime(
            days_offset=-index,
            hours_offset=-1,
        )

        anomalies.append(
            {
                "id": anomaly_id,
                "product_id": product["id"],
                # "forecast_id": forecast["id"] if forecast else "",
                "anomaly_type": str(scenario["anomaly_type"]),
                "metric_name": str(scenario["metric_name"]),
                "actual_value": money(actual_value),
                "expected_value": money(expected_value),
                "deviation_percent": _deviation_percentage(
                    actual_value,
                    expected_value,
                ),
                "impact_value": money(actual_value - expected_value),
                "impact_unit": str(scenario["impact_unit"]),
                "severity": str(scenario["severity"]),
                "period_start": utc_datetime(
                    days_offset=-(2*index),
                    hours_offset=-3,
                ),
                "period_end": utc_datetime(
                    days_offset=-(2*index),
                    hours_offset=+3,
                ),
                "detected_at": utc_datetime(
                    days_offset=-index,
                    hours_offset=-3,
                ),
                # "status": "open",
            }
        )

        alerts.append(
            {
                "id": alert_id,
                "product_id": product["id"],
                "anomaly_id": anomaly_id,
                "assigned_to_user_id": _assigned_to_user_id(
                    users,
                    str(scenario["alert_type"]),
                ),
                "alert_type": str(scenario["alert_type"]),
                "severity": str(scenario["severity"]),
                "status": _alert_status(product["sku"]),
                "title": f"{scenario['alert_type']} for {product['sku']}",
                "recommended_action": str(scenario["recommendation_type"]),
                "created_at": utc_datetime(
                    days_offset=-index,
                    hours_offset=-2,
                ),
                "updated_at": utc_datetime(days_offset=+index),
                # "description": f"Demo scenario for {product['name']}.",
            }
        )

        recommendations.append(
            {
                "id": recommendation_id,
                "product_id": product["id"],
                "forecast_id": "",
                "anomaly_id": anomaly_id,
                "alert_id": alert_id,
                "recommendation_type": str(scenario["recommendation_type"]),
                "recommended_action": (
                    f"Review {product['sku']} and take corrective action."
                ),
                "rationale": str(scenario["rationale"]),
                "status": str(recommendation_status),
                # "priority": str(scenario["severity"]),
                # "recommended_action": (
                #     f"Review {product['sku']} and take corrective action."
                # ),
                # "expected_impact": (
                #     "Improve operational response time for the affected "
                #     "product."
                # ),
                # "confidence_score": confidence(0.80 - index * 0.04),
                "generated_at": recommendation_date,
                "expires_at": None,
                "created_at": recommendation_date,
                # "accepted_at": utc_datetime(
                #     days_offset=-index,
                #     hours_offset=1,
                # )
                # if recommendation_status == "accepted"
                # else "",
            }
        )

        workflow_actions.append(
            {
                "id": workflow_action_id,
                "alert_id": alert_id,
                "performed_by_user_id": actor["id"],
                "action_type": str(scenario["action_type"]),
                "comment": str(scenario["comment"]),
                "previous_status": None,
                "new_status": str(scenario["workflow_status"]),
                "performed_at": None,
                "created_at": utc_datetime(
                    days_offset=-index,
                    hours_offset=2,
                ),
            }
        )

    return {
        "anomalies": anomalies,
        "alerts": alerts,
        "recommendations": recommendations,
        "workflow_actions": workflow_actions,
    }
