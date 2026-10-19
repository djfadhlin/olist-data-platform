import pandas as pd

from olist.quality import check_h02_orders_unique


def main():
    print("=== HARD RULE H02 TEST ===")

    source = pd.DataFrame({
        "order_id": [
            "order_001",
            "order_002",
            "order_001",
            "order_003",
            "order_002",
            "",
            None,
        ],
    })

    violations = check_h02_orders_unique(source)

    print(violations.to_string(index=False))

    assert len(violations) == 2
    assert set(violations["source_row"]) == {2, 4}
    assert set(violations["rule_id"]) == {"H02"}

    print("\nH02 test: PASS")


if __name__ == "__main__":
    main()