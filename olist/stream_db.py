
"""DDL PostgreSQL untuk Kafka streaming Olist."""

import psycopg


STREAM_DDL = """
CREATE SCHEMA IF NOT EXISTS stream;

CREATE TABLE IF NOT EXISTS stream.order_events (
    event_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    status TEXT NOT NULL,
    status_rank INTEGER NOT NULL,
    event_ts TIMESTAMPTZ NOT NULL,
    produced_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stream_events_order_id
    ON stream.order_events (order_id);

CREATE TABLE IF NOT EXISTS stream.order_current (
    order_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    status_rank INTEGER NOT NULL,
    event_id TEXT NOT NULL,
    event_ts TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stream.order_dlq (
    id BIGSERIAL PRIMARY KEY,
    topic TEXT NOT NULL,
    partition_id INTEGER NOT NULL,
    offset_id BIGINT NOT NULL,
    raw_payload BYTEA,
    error_reason TEXT NOT NULL,
    consumed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (topic, partition_id, offset_id)
);
"""


def create_stream_schema(conn: psycopg.Connection) -> None:
    """Buat schema dan tabel stream secara idempoten."""
    with conn.cursor() as cur:
        cur.execute(STREAM_DDL)


def verify_stream_schema(conn: psycopg.Connection) -> None:
    """Pastikan semua tabel stream tersedia."""

    expected = {
        "order_events",
        "order_current",
        "order_dlq",
    }

    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'stream'
              AND table_type = 'BASE TABLE'
        """)

        actual = {row[0] for row in cur.fetchall()}

    missing = expected - actual

    if missing:
        raise RuntimeError(
            f"Missing stream tables: {sorted(missing)}"
        )

    print("PASS: stream.order_events")
    print("PASS: stream.order_current")
    print("PASS: stream.order_dlq")
