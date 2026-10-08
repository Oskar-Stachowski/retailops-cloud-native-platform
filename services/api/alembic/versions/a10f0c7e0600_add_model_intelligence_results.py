"""Add native anomaly/risk projections and preserve all existing transport receipts."""

from alembic import op

revision = "a10f0c7e0600"
down_revision = "a10f0c7e0500"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE ai_model_results (
 result_id text PRIMARY KEY,
 event_type text NOT NULL CHECK(event_type IN ('anomaly_detected','stockout_risk_scored')),
 product_id text NOT NULL,
 selling_location_id text,
 stock_location_id text,
 channel text CHECK(channel IN ('store','online','marketplace','wholesale')),
 currency text CHECK(currency IN ('PLN','EUR')),
 as_of timestamptz NOT NULL,
 generated_at timestamptz NOT NULL CHECK(generated_at>=as_of),
 model_name text NOT NULL,
 model_version text NOT NULL,
 release_id text NOT NULL,
 inference_run_id text NOT NULL,
 source_dataset_id text NOT NULL,
 payload jsonb NOT NULL CHECK(octet_length(payload::text)<=32768),
 payload_sha256 text NOT NULL CHECK(payload_sha256 ~ '^[0-9a-f]{64}$'),
 received_at timestamptz NOT NULL DEFAULT now(),
 CHECK((payload->>'product_id'=product_id AND payload->>'release_id'=release_id
  AND payload->>'inference_run_id'=inference_run_id
  AND (payload->>'as_of')::timestamptz=as_of
  AND (payload->>'generated_at')::timestamptz=generated_at) IS TRUE),
 CHECK(((event_type='anomaly_detected' AND result_id ~ '^anomaly-sha256-[0-9a-f]{64}$'
  AND selling_location_id IS NOT NULL AND channel IS NOT NULL AND currency IS NOT NULL
  AND stock_location_id IS NULL AND payload->>'anomaly_id'=result_id
  AND payload->>'selling_location_id'=selling_location_id AND payload->>'channel'=channel
  AND payload->>'currency'=currency AND payload->>'detector_name'=model_name
  AND payload->>'detector_version'=model_version AND payload->>'source_dataset_id'=source_dataset_id)
 OR (event_type='stockout_risk_scored' AND result_id ~ '^risk-sha256-[0-9a-f]{64}$'
  AND stock_location_id IS NOT NULL AND selling_location_id IS NULL AND channel IS NULL AND currency IS NULL
  AND payload->>'risk_id'=result_id AND payload->>'stock_location_id'=stock_location_id
  AND payload->>'model_name'=model_name AND payload->>'model_version'=model_version
  AND payload->'lineage'->>'source_dataset_id'=source_dataset_id)) IS TRUE)
);
CREATE INDEX ai_model_results_sales_scope ON ai_model_results
 (event_type,product_id,selling_location_id,channel,currency,as_of DESC,result_id);
CREATE INDEX ai_model_results_physical_scope ON ai_model_results
 (event_type,product_id,stock_location_id,as_of DESC,result_id);
CREATE TABLE ai_model_intelligence_inbox (
 event_id uuid PRIMARY KEY,
 result_id text NOT NULL REFERENCES ai_model_results(result_id),
 document_sha256 text NOT NULL CHECK(document_sha256 ~ '^[0-9a-f]{64}$'),
 processed_at timestamptz NOT NULL DEFAULT now()
);
CREATE FUNCTION ai_model_projection_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'intelligence_model_projection_immutable' USING ERRCODE='23514';
END $$;
CREATE TRIGGER ai_model_result_immutable BEFORE UPDATE OR DELETE ON ai_model_results
 FOR EACH ROW EXECUTE FUNCTION ai_model_projection_immutable();
CREATE TRIGGER ai_model_inbox_immutable BEFORE UPDATE OR DELETE ON ai_model_intelligence_inbox
 FOR EACH ROW EXECUTE FUNCTION ai_model_projection_immutable();
ALTER TABLE ai_intelligence_transport ADD COLUMN model_result_id text
 REFERENCES ai_model_results(result_id);
ALTER TABLE ai_intelligence_transport DROP CONSTRAINT ai_intelligence_transport_result;
ALTER TABLE ai_intelligence_transport ADD CONSTRAINT ai_intelligence_transport_result CHECK(
 (outcome='quarantined' AND quarantine_id IS NOT NULL
  AND num_nonnulls(prediction_id,recommendation_id,model_result_id)=0)
 OR (outcome IN ('projected','duplicate') AND quarantine_id IS NULL
  AND num_nonnulls(prediction_id,recommendation_id,model_result_id)=1)
);
""")


def downgrade():
    op.execute("""
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM ai_model_results)
  OR EXISTS(SELECT 1 FROM ai_intelligence_transport WHERE model_result_id IS NOT NULL)
 THEN RAISE EXCEPTION 'model_schema_downgrade_requires_empty_projection'; END IF;
END $$;
ALTER TABLE ai_intelligence_transport DROP CONSTRAINT ai_intelligence_transport_result;
ALTER TABLE ai_intelligence_transport DROP COLUMN model_result_id;
ALTER TABLE ai_intelligence_transport ADD CONSTRAINT ai_intelligence_transport_result CHECK(
 (outcome='quarantined' AND quarantine_id IS NOT NULL AND prediction_id IS NULL AND recommendation_id IS NULL)
 OR (outcome IN ('projected','duplicate') AND quarantine_id IS NULL
  AND num_nonnulls(prediction_id,recommendation_id)=1)
);
DROP TABLE ai_model_intelligence_inbox;
DROP TABLE ai_model_results;
DROP FUNCTION ai_model_projection_immutable();
""")
