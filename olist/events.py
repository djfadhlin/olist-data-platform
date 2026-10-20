
"""Model event streaming Olist.

Membangun event deterministik dari baris raw Orders.
Tidak membutuhkan Kafka atau PostgreSQL saat unit test.
"""

import hashlib
from datetime import datetime, timezone


STATUS_RANK = {
    "created": 10,
    "approved": 20,
    "invoiced": 25,
    "processing": 30,
    "shipped": 40,
    "delivered": 50,
    "canceled": 60,
    "unavailable": 60,
}


def make_event_id(order_id: str, status: str) -> str:
    """ID deterministik untuk satu transisi status order."""

    payload = f"{order_id}|{status}".encode("utf-8")

    return hashlib.sha256(payload).hexdigest()


def parse_event_time(value):
    """Normalisasi timestamp sumber menjadi ISO 8601 UTC.

    Tanggal Olist tidak menyertakan timezone.
    Untuk replay ini diasumsikan UTC dan dicatat sebagai
    keputusan desain, bukan klaim timezone sumber.
    """

    if value is None or str(value).strip() == "":
        return None

    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()

    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.strptime(
            str(value),
            "%Y-%m-%d %H:%M:%S",
        )

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc).isoformat()


def build_order_events(order: dict) -> list[dict]:
    """Buat event sesuai timestamp dan status akhir sumber."""

    order_id = str(order["order_id"]).strip()
    final_status = str(order["order_status"]).strip()

    if not order_id:
        raise ValueError("order_id wajib terisi")

    if final_status not in STATUS_RANK:
        raise ValueError(f"Unknown order status: {final_status}")

    candidates = [
        ("created", "order_purchase_timestamp"),
        ("approved", "order_approved_at"),
        ("shipped", "order_delivered_carrier_date"),
        ("delivered", "order_delivered_customer_date"),
    ]

    events = []

    for status, column in candidates:
        # Jangan menghasilkan status yang lebih tinggi daripada
        # tahap final untuk status progres normal.
        if final_status not in ("canceled", "unavailable"):
            if STATUS_RANK[status] > STATUS_RANK[final_status]:
                continue

        event_ts = parse_event_time(order.get(column))

        if event_ts is None:
            continue

        events.append({
            "event_id": make_event_id(order_id, status),
            "order_id": order_id,
            "status": status,
            "status_rank": STATUS_RANK[status],
            "event_ts": event_ts,
        })

    # Untuk canceled/unavailable, buat event terminal
    # dengan timestamp paling akhir yang tersedia.
    # Olist tidak menyediakan canceled_at tersendiri.
    if final_status in ("canceled", "unavailable"):
        if not events:
            raise ValueError(
                f"No timestamp available for {order_id}"
            )

        terminal_ts = max(
            event["event_ts"] for event in events
        )

        events.append({
            "event_id": make_event_id(order_id, final_status),
            "order_id": order_id,
            "status": final_status,
            "status_rank": STATUS_RANK[final_status],
            "event_ts": terminal_ts,
        })

    # Jika status final belum direpresentasikan karena
    # timestamp terkait kosong, catat anomali secara eksplisit.
    if final_status not in {
        event["status"] for event in events
    }:
        if not events:
            raise ValueError(
                f"No valid timestamps for {order_id}"
            )

        last_ts = max(event["event_ts"] for event in events)

        events.append({
            "event_id": make_event_id(order_id, final_status),
            "order_id": order_id,
            "status": final_status,
            "status_rank": STATUS_RANK[final_status],
            "event_ts": last_ts,
        })

    # Producer membangun urutan berdasarkan event time.
    # Consumer tetap wajib tahan terhadap urutan kedatangan
    # yang berbeda.
    events.sort(
        key=lambda event: (
            event["event_ts"],
            event["status_rank"],
        )
    )

    return events
