
"""Event replay dan controlled fault injection untuk Olist.

Fungsi di modul ini tidak membutuhkan koneksi Kafka.
Pesan Kafka direpresentasikan sebagai dict dengan key dan value bytes.
"""

import json
import random
from collections import Counter
from datetime import datetime, timezone

from olist.events import build_order_events


def make_replay_messages(
    orders: list[dict],
    seed: int = 42,
    duplicate_rate: float = 0.03,
    late_rate: float = 0.02,
    corrupt_rate: float = 0.005,
    produced_at: str | None = None,
):
    """Bangun pesan replay dan manifest gangguan.

    - Duplicate: pesan valid identik dikirim dua kali.
    - Late: pesan ditahan dan dikirim setelah aliran utama.
    - Corrupt: pesan rusak yang diharapkan masuk DLQ.

    Seed mengontrol pemilihan gangguan.
    produced_at dapat dikunci untuk unit test.
    """

    for name, rate in (
        ("duplicate_rate", duplicate_rate),
        ("late_rate", late_rate),
        ("corrupt_rate", corrupt_rate),
    ):
        if not 0 <= rate <= 1:
            raise ValueError(
                f"{name} must be between 0 and 1"
            )

    if duplicate_rate + late_rate + corrupt_rate > 1:
        raise ValueError(
            "Sum of injection rates cannot exceed 1"
        )

    rng = random.Random(seed)

    events = []

    for order in orders:
        events.extend(build_order_events(order))

    # Urutkan berdasarkan waktu kejadian.
    events.sort(
        key=lambda event: (
            event["event_ts"],
            event["order_id"],
            event["status_rank"],
            event["event_id"],
        )
    )

    total = len(events)

    duplicate_count = round(total * duplicate_rate)
    late_count = round(total * late_rate)
    corrupt_count = round(total * corrupt_rate)

    # Tiga kelompok dibuat tidak tumpang tindih.
    indexes = list(range(total))
    rng.shuffle(indexes)

    duplicate_indexes = set(indexes[:duplicate_count])

    late_indexes = set(
        indexes[
            duplicate_count:
            duplicate_count + late_count
        ]
    )

    corrupt_indexes = set(
        indexes[
            duplicate_count + late_count:
            duplicate_count + late_count + corrupt_count
        ]
    )

    if produced_at is None:
        produced_at = datetime.now(
            timezone.utc
        ).isoformat()

    messages = []
    delayed_messages = []
    corruption_types = Counter()

    for index, event in enumerate(events):
        payload = {
            **event,
            "produced_at": produced_at,
        }

        if index in corrupt_indexes:
            corruption_type = index % 3

            if corruption_type == 0:
                # Hilangkan field wajib.
                payload.pop("event_id")

                encoded = json.dumps(
                    payload
                ).encode("utf-8")

                corruption_types["missing_field"] += 1

            elif corruption_type == 1:
                # Format timestamp tidak valid.
                payload["event_ts"] = "not-a-timestamp"

                encoded = json.dumps(
                    payload
                ).encode("utf-8")

                corruption_types["invalid_timestamp"] += 1

            else:
                # JSON terpotong.
                encoded = b'{"broken_json":'

                corruption_types["invalid_json"] += 1

        else:
            encoded = json.dumps(
                payload
            ).encode("utf-8")

        message = {
            "key": event["order_id"].encode("utf-8"),
            "value": encoded,
        }

        if index in late_indexes:
            delayed_messages.append(message)
        else:
            messages.append(message)

        if index in duplicate_indexes:
            # Duplikat benar-benar identik byte-for-byte.
            duplicate = {
                "key": message["key"],
                "value": message["value"],
            }
            messages.append(duplicate)

    # Event yang ditahan muncul setelah aliran utama.
    messages.extend(delayed_messages)

    manifest = {
        "seed": seed,
        "orders": len(orders),
        "base_events": total,
        "unique_valid_events": total - corrupt_count,
        "duplicate_injections": duplicate_count,
        "late_injections": late_count,
        "corrupt_injections": corrupt_count,
        "corruption_types": dict(corruption_types),
        "total_messages": len(messages),
        "produced_at": produced_at,
    }

    return messages, manifest
