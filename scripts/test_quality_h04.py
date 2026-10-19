import pandas as pd

from olist.quality import check_h04_order_items_key


def main():
    print("=== HARD RULE H04 TEST ===")

    source = pd.DataFrame({
        "order_id": [
            "order_001",
            "order_001",
            "order_002",
            "",
            "order_003",
            "order_004",
        ],
        "order_item_id": [
            "1",
            "1",
            "2",
            "1",
            None,
            "2.5",
        ],
    })

    violations = check_h04_order_items_key(source)

    print(violations.to_string(index=False))

    assert len(violations) == 4
    assert set(violations["source_row"]) == {1, 3, 4, 5}
    assert set(violations["rule_id"]) == {"H04"}

    print("\nH04 test: PASS")


if __name__ == "__main__":
    main()