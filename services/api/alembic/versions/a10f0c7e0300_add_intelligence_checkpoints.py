"""Add transport receipts and fenced partition cursors; preserve the existing projection."""

from alembic import op

revision = "a10f0c7e0300"
down_revision = "a10f0c7e0200"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE ai_intelligence_partitions (
 consumer_group text NOT NULL,
 topic text NOT NULL CHECK(topic='retailops.intelligence.v2'),
 partition integer NOT NULL CHECK(partition >= 0),
 cluster_id text NOT NULL,
 topic_id text NOT NULL,
 coverage_start bigint NOT NULL CHECK(coverage_start >= 0),
 next_offset bigint NOT NULL CHECK(next_offset >= coverage_start),
 initial_policy text NOT NULL CHECK(initial_policy IN ('broker_commit','log_low')),
 epoch bigint NOT NULL DEFAULT 0 CHECK(epoch >= 0),
 owner_id uuid,
 claimed_at timestamptz,
 checkpoint_at timestamptz,
 PRIMARY KEY(consumer_group,topic,partition)
);
CREATE TABLE ai_intelligence_transport (
 consumer_group text NOT NULL,
 topic text NOT NULL,
 partition integer NOT NULL,
 offset_number bigint NOT NULL CHECK(offset_number >= 0),
 raw_sha256 text NOT NULL CHECK(raw_sha256 ~ '^[0-9a-f]{64}$'),
 outcome text NOT NULL CHECK(outcome IN ('projected','duplicate','quarantined')),
 prediction_id text REFERENCES ai_forecast_results(prediction_id),
 quarantine_id uuid REFERENCES realtime_event_log(event_id),
 processed_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(consumer_group,topic,partition,offset_number),
 FOREIGN KEY(consumer_group,topic,partition)
   REFERENCES ai_intelligence_partitions(consumer_group,topic,partition),
 CHECK((outcome='quarantined' AND quarantine_id IS NOT NULL AND prediction_id IS NULL)
    OR (outcome IN ('projected','duplicate') AND prediction_id IS NOT NULL AND quarantine_id IS NULL))
);
""")


def downgrade():
    op.execute("DROP TABLE ai_intelligence_transport; DROP TABLE ai_intelligence_partitions;")
