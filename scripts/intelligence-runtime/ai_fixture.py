# ruff: noqa: INP001
"""Initialize an invented outbox prerequisite, NOT a model publication or approval.

The output parent is a storage double. Only the actual pinned 0020 migration and
deliver_one worker are under acceptance here. Full ML publication is a separate gate.
"""

import importlib
import json
import os
import sys
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from retailops_ai.intelligence_events.contracts import ForecastGenerated
from sqlalchemy import create_engine, text


def main() -> None:
    event = ForecastGenerated.model_validate_json(Path("/ai/fixture.json").read_bytes())
    if event.payload.model_name != "retailops-demand-forecast-v12-mechanics":
        msg = "explicit_mechanics_fixture_required"
        raise RuntimeError(msg)
    engine = create_engine(os.environ["DATABASE_URL"], hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA ai"))
        connection.execute(
            text("CREATE TABLE ai.v12_forecast_outputs(artifact_id text PRIMARY KEY)")
        )
        module = importlib.import_module(
            "retailops_ai.migrations.versions.0020_intelligence_outbox"
        )
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        connection.execute(
            text("INSERT INTO ai.v12_forecast_outputs VALUES (:id)"),
            {"id": event.payload.prediction_dataset_id},
        )
        connection.execute(
            text("""INSERT INTO ai.intelligence_outbox
            (event_id,artifact_id,environment,topic,partition_key,document)
            VALUES (:id,:artifact,'test',:topic,:key,CAST(:document AS jsonb))"""),
            {
                "id": str(event.event_id),
                "artifact": event.payload.prediction_dataset_id,
                "topic": event.topic,
                "key": event.partition_key,
                "document": event.model_dump_json(),
            },
        )
        connection.execute(text("GRANT USAGE ON SCHEMA ai TO ai_worker"))
        connection.execute(text("GRANT SELECT,UPDATE ON ai.intelligence_outbox TO ai_worker"))
    engine.dispose()
    sys.stdout.write(
        json.dumps({"status": "prepared", "evidence_class": "invented_transport_fixture"}) + "\n"
    )


if __name__ == "__main__":
    main()
