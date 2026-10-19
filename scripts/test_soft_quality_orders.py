
import pandas as pd

from olist.soft_quality import check_orders_soft_rules


def main():
    print("=== SOFT RULES S01-S03 TEST ===")

    source = pd.DataFrame({
        "order_status": [
            "delivered",
            "delivered",
            "approved",
            "delivered",
        ],
        "order_purchase_timestamp": [
            "2018-01-01 10:00:00",
            "2018-01-02 10:00:00",
            "2018-01-03 10:00:00",
            "2018-01-04 10:00:00",
        ],
        "order_approved_at": [
            "2018-01-01 11:00:00",
            "2018-01-02 11:00:00",
            "2018-01-03 09:00:00",
            "2018-01-04 11:00:00",
        ],
        "order_delivered_carrier_date": [
            "2018-01-02 10:00:00",
            "2018-01-05 10:00:00",
            None,
            "2018-01-05 10:00:00",
        ],
        "order_delivered_customer_date": [
            None,
            "2018-01-04 10:00:00",
            None,
            "2018-01-06 10:00:00",
        ],
    })

    violations = check_orders_soft_rules(source)

    counts = violations.groupby("rule_id").size().to_dict()

    print(violations.to_string(index=False))
    print("\nCounts:", counts)

    assert counts == {
        "S01": 1,
        "S02": 1,
        "S03": 1,
    }

    assert set(violations["source_row"]) == {0, 1, 2}

    # Soft rules tidak mengurangi jumlah record.
    assert len(source) == 4

    print("\nSoft rules S01-S03 test: PASS")


if __name__ == "__main__":
    main()
