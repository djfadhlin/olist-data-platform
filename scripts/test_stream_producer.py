
"""Unit test producer Olist: determinisme dan fault injection."""

import json

from olist.stream_producer import make_replay_messages


def make_order(number: int) -> dict:
    return {
        "order_id": f"test_{number:05d}",
        "order_status": "delivered",
        "order_purchase_timestamp": "2018-01-01 10:00:00",
        "order_approved_at": "2018-01-01 11:00:00",
        "order_delivered_carrier_date": "2018-01-02 10:00:00",
        "order_delivered_customer_date": "2018-01-05 10:00:00",
    }


def main():
    print("=== T3 PRODUCER INJECTION TEST ===")

    orders = [
        make_order(i)
        for i in range(200)
    ]

    fixed_time = "2026-10-20T08:00:00+00:00"

    first_messages, first = make_replay_messages(
        orders,
        seed=42,
        produced_at=fixed_time,
    )

    second_messages, second = make_replay_messages(
        orders,
        seed=42,
        produced_at=fixed_time,
    )

    # 1. Replay deterministik.
    assert first == second
    assert first_messages == second_messages

    print("Deterministic replay: PASS")

    # 2. Jumlah event dasar.
    assert first["orders"] == 200
    assert first["base_events"] == 800

    # 3. Persentase gangguan.
    assert first["duplicate_injections"] == 24
    assert first["late_injections"] == 16
    assert first["corrupt_injections"] == 4

    # 4. Total pesan termasuk duplikat.
    assert first["total_messages"] == 824
    assert len(first_messages) == 824

    # 5. Corrupt events tidak termasuk event valid.
    assert first["unique_valid_events"] == 796

    # 6. Semua Kafka message menggunakan key bytes.
    assert all(
        isinstance(message["key"], bytes)
        and isinstance(message["value"], bytes)
        for message in first_messages
    )

    # 7. Pesan valid mempunyai produced_at yang sama.
    valid_messages = []

    for message in first_messages:
        try:
            payload = json.loads(
                message["value"].decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue

        if (
            isinstance(payload, dict)
            and "event_id" in payload
            and payload.get("event_ts") != "not-a-timestamp"
        ):
            valid_messages.append(payload)

    assert valid_messages

    assert all(
        payload["produced_at"] == fixed_time
        for payload in valid_messages
    )

    # 8. Jumlah kerusakan sesuai manifest.
    assert sum(
        first["corruption_types"].values()
    ) == 4

    # 9. Mengubah seed mengubah pemilihan gangguan.
    different_messages, different_manifest = (
        make_replay_messages(
            orders,
            seed=99,
            produced_at=fixed_time,
        )
    )

    assert (
        different_messages != first_messages
    )

    assert (
        different_manifest["total_messages"]
        == first["total_messages"]
    )

    print(f"Base events: {first['base_events']:,}")
    print(
        "Duplicate injections:",
        first["duplicate_injections"],
    )
    print(
        "Late injections:",
        first["late_injections"],
    )
    print(
        "Corrupt injections:",
        first["corrupt_injections"],
    )
    print(
        "Total Kafka messages:",
        first["total_messages"],
    )

    print("Fault injection counts: PASS")
    print("Kafka message format: PASS")
    print("Seed variation: PASS")

    print("\nT3 producer injection logic: PASS")


if __name__ == "__main__":
    main()
