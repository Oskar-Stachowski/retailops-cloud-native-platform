"""Persist source observation history and its atomic publication outbox."""

from alembic import op

revision = "a10f0c7e0500"
down_revision = "a10f0c7e0400"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE source_observation_streams (
 authority_id uuid PRIMARY KEY,
 cluster_id text NOT NULL,
 topic_id text NOT NULL,
 partitions integer NOT NULL CHECK(partitions BETWEEN 1 AND 32),
 UNIQUE(cluster_id,topic_id)
);
CREATE TABLE source_observation_keys (
 authority_id uuid NOT NULL REFERENCES source_observation_streams(authority_id),
 observation_id uuid NOT NULL,
 business_date date NOT NULL,
 product_id uuid NOT NULL,
 selling_location_id uuid NOT NULL,
 channel text NOT NULL CHECK(channel IN ('store','online','marketplace','wholesale')),
 latest_version bigint NOT NULL CHECK(latest_version >= 1),
 latest_available_at timestamptz NOT NULL,
 PRIMARY KEY(authority_id,observation_id),
 UNIQUE(authority_id,business_date,product_id,selling_location_id,channel)
);
CREATE TABLE source_observation_versions (
 authority_id uuid NOT NULL,
 observation_id uuid NOT NULL,
 version bigint NOT NULL CHECK(version >= 1),
 row_id uuid NOT NULL,
 fact_bytes bytea NOT NULL CHECK(octet_length(fact_bytes) BETWEEN 1 AND 8192),
 fact_sha256 text NOT NULL CHECK(fact_sha256 ~ '^[0-9a-f]{64}$'),
 PRIMARY KEY(authority_id,observation_id,version),
 UNIQUE(authority_id,row_id),
 FOREIGN KEY(authority_id,observation_id) REFERENCES source_observation_keys(authority_id,observation_id)
);
CREATE TABLE source_observation_outbox (
 sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 authority_id uuid NOT NULL,
 observation_id uuid NOT NULL,
 version bigint NOT NULL,
 event_id uuid NOT NULL UNIQUE,
 partition integer NOT NULL CHECK(partition BETWEEN 0 AND 31),
 event_bytes bytea NOT NULL CHECK(octet_length(event_bytes) BETWEEN 1 AND 16384),
 event_sha256 text NOT NULL CHECK(event_sha256 ~ '^[0-9a-f]{64}$'),
 delivered_offset bigint CHECK(delivered_offset >= 0),
 delivered_at timestamptz,
 CHECK((delivered_offset IS NULL) = (delivered_at IS NULL)),
 FOREIGN KEY(authority_id,observation_id,version) REFERENCES source_observation_versions(authority_id,observation_id,version),
 UNIQUE(authority_id,observation_id,version),
 UNIQUE(authority_id,partition,delivered_offset)
);
CREATE INDEX source_observation_outbox_pending ON source_observation_outbox(authority_id,sequence)
 WHERE delivered_offset IS NULL;
""")


def downgrade():
    op.execute("""
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM source_observation_streams) THEN
  RAISE EXCEPTION 'observation_schema_downgrade_requires_empty_streams';
 END IF;
END $$;
DROP TABLE source_observation_outbox;
DROP TABLE source_observation_versions;
DROP TABLE source_observation_keys;
DROP TABLE source_observation_streams;
""")
