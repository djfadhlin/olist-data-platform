
import pandas as pd

from olist.quality import collect_all_hard_violations
from olist.silver import (
    parse_table,
    quarantine_parse_failures,
)


def main():
    print("=== FULL HARD QUALITY TEST ===")

    source = pd.DataFrame({
        "order_id": [
            "order_001",
            "order_001",
            "",
            "order_004",
        ],
        "customer_id": [
            "customer_001",
            "customer_002",
            "customer_003",
            "customer_004",
        ],
        "order_status": [
            "delivered",
            "delivered",
            "created",
            "shipped",
        ],
        "order_purchase_timestamp": [
            "2018-01-01 10:00:00",
            "2018-01-02 10:00:00",
            "2018-01-03 10:00:00",
            "not-a-date",
        ],
        "order_approved_at": [None] * 4,
        "order_delivered_carrier_date": [None] * 4,
        "order_delivered_customer_date": [None] * 4,
        "order_estimated_delivery_date": [
            "2018-01-10 10:00:00",
            "2018-01-11 10:00:00",
            "2018-01-12 10:00:00",
            "2018-01-13 10:00:00",
        ],
    })

    table_name = "olist_orders_dataset"

    parsed = parse_table(source, table_name)

    violations = collect_all_hard_violations(
        source,
        parsed,
        table_name,
    )

    silver, quarantine = quarantine_parse_failures(
        source,
        parsed,
        violations,
        table_name,
    )

    counts = violations.groupby("rule_id").size().to_dict()

    print("Violations per rule:", counts)
    print("Source rows:", len(source))
    print("Silver rows:", len(silver))
    print("Quarantine rows:", len(quarantine))

    print("\n=== QUARANTINE ===")
    print(
        quarantine[
            ["source_row", "order_id", "reason"]
        ].to_string(index=False)
    )

    assert counts == {"H01": 1, "H02": 1, "H03": 1}
    assert len(source) == 4
    assert len(silver) == 1
    assert len(quarantine) == 3
    assert len(source) == len(silver) + len(quarantine)

    print("\nFull hard quality test: PASS")


if __name__ == "__main__":
    main()
