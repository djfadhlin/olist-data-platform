import pandas as pd

from olist.quality import run_hard_rules


def main():
    print("=== HARD RULES INTEGRATION TEST ===")

    orders = pd.DataFrame({
        "order_id": [
            "order_001",
            "order_001",
            "",
            "order_004",
        ],
        "order_purchase_timestamp": [
            "2018-01-01 10:00:00",
            "2018-01-02 10:00:00",
            "2018-01-03 10:00:00",
            "not-a-date",
        ],
    })

    violations = run_hard_rules(
        orders,
        "olist_orders_dataset",
    )

    print(violations.to_string(index=False))

    counts = violations.groupby("rule_id").size().to_dict()

    assert counts == {
        "H01": 1,
        "H02": 1,
        "H03": 1,
    }

    # Ada 3 baris bermasalah, masing-masing satu pelanggaran.
    assert set(violations["source_row"]) == {1, 2, 3}

    print("\nViolations per rule:", counts)
    print("Hard rules integration test: PASS")


if __name__ == "__main__":
    main()