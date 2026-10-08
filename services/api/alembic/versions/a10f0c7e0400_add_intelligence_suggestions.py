"""Add immutable suggestions; retain the forecast transport path during image rollback."""

from alembic import op

revision = "a10f0c7e0400"
down_revision = "a10f0c7e0300"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE ai_recommendation_results (
 recommendation_id uuid PRIMARY KEY,
 trace_id uuid NOT NULL,
 answer_id uuid NOT NULL,
 candidate_id text NOT NULL,
 product_id text NOT NULL,
 selling_location_id text NOT NULL,
 channel text NOT NULL CHECK(channel IN ('store','online')),
 policy_sha256 text NOT NULL,
 agent_config_version text NOT NULL,
 created_at timestamptz NOT NULL,
 expires_at timestamptz NOT NULL CHECK(expires_at > created_at),
 payload jsonb NOT NULL,
 payload_sha256 text NOT NULL CHECK(payload_sha256 ~ '^[0-9a-f]{64}$'),
 received_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ai_recommendation_results_scope ON ai_recommendation_results
 (product_id,selling_location_id,channel,created_at DESC,recommendation_id);
CREATE TABLE ai_recommendation_inbox (
 event_id uuid PRIMARY KEY,
 recommendation_id uuid NOT NULL REFERENCES ai_recommendation_results(recommendation_id),
 document_sha256 text NOT NULL CHECK(document_sha256 ~ '^[0-9a-f]{64}$'),
 processed_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE ai_intelligence_transport ADD COLUMN recommendation_id uuid
 REFERENCES ai_recommendation_results(recommendation_id);
ALTER TABLE ai_intelligence_transport DROP CONSTRAINT ai_intelligence_transport_check;
ALTER TABLE ai_intelligence_transport ADD CONSTRAINT ai_intelligence_transport_result CHECK(
 (outcome='quarantined' AND quarantine_id IS NOT NULL AND prediction_id IS NULL AND recommendation_id IS NULL)
 OR (outcome IN ('projected','duplicate') AND quarantine_id IS NULL
     AND ((prediction_id IS NOT NULL AND recommendation_id IS NULL)
       OR (prediction_id IS NULL AND recommendation_id IS NOT NULL)))
);
""")


def downgrade():
    # An application rollback preserves the expanded schema. Explicit schema downgrade
    # refuses populated suggestion receipts, rather than discarding acknowledged data.
    op.execute("""
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM ai_recommendation_results)
    OR EXISTS(SELECT 1 FROM ai_intelligence_transport WHERE recommendation_id IS NOT NULL)
 THEN RAISE EXCEPTION 'suggestion_schema_downgrade_requires_empty_projection'; END IF;
END $$;
ALTER TABLE ai_intelligence_transport DROP CONSTRAINT ai_intelligence_transport_result;
ALTER TABLE ai_intelligence_transport DROP COLUMN recommendation_id;
ALTER TABLE ai_intelligence_transport ADD CONSTRAINT ai_intelligence_transport_check CHECK(
 (outcome='quarantined' AND quarantine_id IS NOT NULL AND prediction_id IS NULL)
 OR (outcome IN ('projected','duplicate') AND prediction_id IS NOT NULL AND quarantine_id IS NULL)
);
DROP TABLE ai_recommendation_inbox;
DROP TABLE ai_recommendation_results;
""")
