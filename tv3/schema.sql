CREATE TABLE IF NOT EXISTS nids_events (
    topic text NOT NULL,
    partition_id integer NOT NULL,
    message_offset bigint NOT NULL,
    observed_at timestamptz NOT NULL DEFAULT now(),
    src_ip text NOT NULL,
    dst_port integer NOT NULL CHECK (dst_port BETWEEN 0 AND 65535),
    protocol integer NOT NULL,
    prediction smallint NOT NULL CHECK (prediction BETWEEN 0 AND 3),
    scenario text NOT NULL,
    demo_id text,
    PRIMARY KEY (topic, partition_id, message_offset)
);
CREATE INDEX IF NOT EXISTS nids_events_observed_at_idx ON nids_events (observed_at DESC);
