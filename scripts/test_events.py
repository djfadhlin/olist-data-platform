
"""Unit test event model T3 tanpa Kafka dan Docker."""

from olist.events import (
    build_order_events,
    make_event_id,
)


def main():
    print("=== T3 EVENT MODEL TEST ===")

    delivered_order = {
        "order_id": "order_001",
        "order_status": "delivered",
        "order_purchase_timestamp": "2018-01-01 10:00:00",
        "order_approved_at": "2018-01-01 11:00:00",
        "order_delivered_carrier_date": "2018-01-02 10:00:00",
        "order_delivered_customer_date": "2018-01-05 10:00:00",
    }

    first = build_order_events(delivered_order)
    second = build_order_events(delivered_order)

    assert len(first) == 4
    assert [event["status"] for event in first] == [
        "created",
        "approved",
        "shipped",
        "delivered",
    ]

    assert [event["event_id"] for event in first] == [
        event["event_id"] for event in second
    ]

    assert len({
        event["event_id"] for event in first
    }) == 4

    assert make_event_id("o1", "created") != (
        make_event_id("o1", "delivered")
    )

    print("Delivered order transitions: PASS")
    print("Deterministic event IDs: PASS")

    canceled_order = {
        "order_id": "order_002",
        "order_status": "canceled",
        "order_purchase_timestamp": "2018-01-01 10:00:00",
        "order_approved_at": None,
        "order_delivered_carrier_date": None,
        "order_delivered_customer_date": None,
    }

    canceled_events = build_order_events(canceled_order)

    assert canceled_events[-1]["status"] == "canceled"

    print("Canceled terminal event: PASS")

    print("\nT3 event model test: PASS")


if __name__ == "__main__":
    main()
