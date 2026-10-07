"""Add separate immutable v2 inbox and forecast projection; legacy tables stay intact."""

from alembic import op

revision = "a10f0c7e0200"
down_revision = "6b0f1c2d3e4a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE ai_forecast_results (
 prediction_id text PRIMARY KEY,
 prediction_dataset_id text NOT NULL,
 product_id text NOT NULL,
 selling_location_id text NOT NULL,
 channel text NOT NULL CHECK(channel IN ('store','online')),
 forecast_origin timestamptz NOT NULL,
 target_date date NOT NULL,
 horizon_days integer NOT NULL CHECK(horizon_days BETWEEN 1 AND 14),
 release_id text NOT NULL,
 inference_run_id text NOT NULL,
 generated_at timestamptz NOT NULL,
 payload jsonb NOT NULL,
 payload_sha256 text NOT NULL,
 received_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ai_forecast_results_scope ON ai_forecast_results
 (product_id,selling_location_id,channel,forecast_origin DESC,prediction_id);
CREATE TABLE ai_intelligence_inbox (
 event_id uuid PRIMARY KEY,
 event_type text NOT NULL CHECK(event_type='forecast_generated'),
 prediction_id text NOT NULL REFERENCES ai_forecast_results(prediction_id),
 document_sha256 text NOT NULL,
 processed_at timestamptz NOT NULL DEFAULT now()
);
""")


def downgrade():
    op.execute("DROP TABLE ai_intelligence_inbox; DROP TABLE ai_forecast_results;")
