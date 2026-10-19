import pandas as pd

from olist.soft_quality import check_cross_table_soft_rules


def main():
    print("=== SOFT RULES S05-S08 TEST ===")

    orders = pd.DataFrame({
        "order_id": ["o1", "o2", "o3", "o4", "o5"],
    })

    items = pd.DataFrame({
        "order_id": ["o1", "o2", "o4", "o5"],
        "price": ["100.00", "50.00", "30.00", "10.00"],
        "freight_value": ["10.00", "5.00", "2.00", "0.00"],
    })

    payments = pd.DataFrame({
        "order_id": ["o1", "o2", "o3", "o4", "o5"],
        "payment_value": [
            "110.00",
            "55.00",
            "20.00",
            "40.00",
            "10.00",
        ],
    })

    reviews = pd.DataFrame({
        "order_id": ["o1", "o1", "o2", "o4"],
        "review_id": ["r1", "r2", "r3", "r4"],
    })

    violations = check_cross_table_soft_rules(
        orders,
        items,
        payments,
        reviews,
    )

    counts = violations.groupby("rule_id").size().to_dict()

    print(violations.to_string(index=False))
    print("\nCounts:", counts)

    assert counts == {
        "S05": 1,
        "S06": 1,
        "S08": 1,
    }

    assert set(
        violations.loc[
            violations["rule_id"] == "S05", "source_row"
        ]
    ) == {0}

    assert set(
        violations.loc[
            violations["rule_id"] == "S06", "source_row"
        ]
    ) == {2}

    assert set(
        violations.loc[
            violations["rule_id"] == "S08", "source_row"
        ]
    ) == {3}

    print("\nSoft rules S05-S08 test: PASS")


if __name__ == "__main__":
    main()