from datetime import datetime, timezone
from uuid import uuid4

from app.repositories.workflow_repository import WorkflowRepository


class FakeCursor:
    def __init__(self, fetchone_results):
        self.fetchone_results = list(fetchone_results)
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((str(query), params))

    def fetchone(self):
        return self.fetchone_results.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.committed = False

    def cursor(self, *args, **kwargs):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_recommendation_workflow_action_uses_native_audit_log_when_alert_linked(
    monkeypatch,
):
    recommendation_id = uuid4()
    alert_id = uuid4()
    actor_id = uuid4()
    now = datetime.now(timezone.utc)
    recommendation_row = {
        "id": recommendation_id,
        "product_id": uuid4(),
        "forecast_id": None,
        "anomaly_id": None,
        "alert_id": alert_id,
        "recommendation_type": "replenish_stock",
        "recommended_action": "Replenish stock",
        "rationale": "Forecasted stockout risk.",
        "status": "accepted",
        "generated_at": now,
        "expires_at": None,
        "created_at": now,
    }
    audit_log_row = {
        "id": uuid4(),
        "entity_type": "recommendation",
        "entity_id": recommendation_id,
        "action_type": "accept",
        "performed_by_user_id": actor_id,
        "assigned_to_user_id": None,
        "previous_status": "proposed",
        "new_status": "accepted",
        "comment": None,
        "idempotency_key": "rec-accept-001",
        "source": "api",
        "details": {"alert_id": str(alert_id)},
        "performed_at": now,
        "created_at": now,
    }
    cursor = FakeCursor([recommendation_row, audit_log_row])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        "app.repositories.workflow_repository.get_connection",
        lambda: connection,
    )

    result = WorkflowRepository().apply_recommendation_workflow_action(
        recommendation_id=recommendation_id,
        alert_id=alert_id,
        action="accept",
        previous_status="proposed",
        new_status="accepted",
        performed_by_user_id=actor_id,
        idempotency_key="rec-accept-001",
    )

    executed_sql = "\n".join(query for query, _params in cursor.executed)
    assert "UPDATE recommendations" in executed_sql
    assert "INSERT INTO workflow_audit_log" in executed_sql
    assert "INSERT INTO workflow_actions" not in executed_sql
    assert result["workflow_action"] is None
    assert result["audit_log"]["details"]["alert_id"] == str(alert_id)
    assert connection.committed is True
