
"""Validasi dan pemrosesan event Olist ke PostgreSQL stream."""

import json
from datetime import datetime, timezone

from olist.events import STATUS_RANK, make_event_id


REQUIRED_FIELDS = {
    "event_id",
    "order_id",
    "status",
    "status_rank",
    "event_ts",
    "produced_at",
}


def validate_event(payload: bytes) -> dict:
    """Decode dan validasi pesan Kafka.

    Raises ValueError jika pesan tidak valid.
    """
    try:
        event = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    if not isinstance(event, dict):
        raise ValueError("Event must be a JSON object")

    missing = REQUIRED_FIELDS - event.keys()

    if missing:
        raise ValueError(
            f"Missing fields: {sorted(missing)}"
        )

    order_id = event["order_id"]
    status = event["status"]

    if not isinstance(order_id, str) or not order_id.strip():
        raise ValueError("Invalid order_id")

    if status not in STATUS_RANK:
        raise ValueError(f"Invalid status: {status}")

    if type(event["status_rank"]) is not int:
        raise ValueError("status_rank must be integer")

    if event["status_rank"] != STATUS_RANK[status]:
        raise ValueError("Incorrect status_rank")

    expected_event_id = make_event_id(order_id, status)

    if event["event_id"] != expected_event_id:
        raise ValueError("Incorrect event_id")

    for field in ("event_ts", "produced_at"):
        value = event[field]

        if not isinstance(value, str):
            raise ValueError(f"{field} must be ISO string")

        try:
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise ValueError(
                f"Invalid {field}: {value}"
            ) from exc

        if parsed.tzinfo is None:
            raise ValueError(
                f"{field} must include timezone"
            )

        event[field] = parsed.astimezone(timezone.utc)

    return event


def process_event(conn, event: dict) -> str:
    """Simpan satu event, tanpa commit otomatis.

    Return: new, duplicate, atau out_of_order.
    Caller bertanggung jawab atas commit/rollback.
    """

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO stream.order_events (
                event_id,
                order_id,
                status,
                status_rank,
                event_ts,
                produced_at
            )
            VALUES (
                %(event_id)s,
                %(order_id)s,
                %(status)s,
                %(status_rank)s,
                %(event_ts)s,
                %(produced_at)s
            )
            ON CONFLICT (event_id) DO NOTHING
            RETURNING event_id
            """,
            event,
        )

        if cur.fetchone() is None:
            return "duplicate"

        cur.execute(
            """
            INSERT INTO stream.order_current (
                order_id,
                status,
                status_rank,
                event_id,
                event_ts
            )
            VALUES (
                %(order_id)s,
                %(status)s,
                %(status_rank)s,
                %(event_id)s,
                %(event_ts)s
            )
            ON CONFLICT (order_id) DO UPDATE
            SET
                status = EXCLUDED.status,
                status_rank = EXCLUDED.status_rank,
                event_id = EXCLUDED.event_id,
                event_ts = EXCLUDED.event_ts,
                updated_at = NOW()
            WHERE
                EXCLUDED.status_rank >
                    stream.order_current.status_rank
            """,
            event,
        )

        if cur.rowcount == 0:
            return "out_of_order"

        return "new"
