import pandas as pd

from olist.quality import check_h01_orders_id


def main():
    print("=== HARD RULE H01 TEST ===")

    source = pd.DataFrame({
        "order_id": ["order_001", "", None, "order_004"],
    })

    violations = check_h01_orders_id(source)

    print(violations.to_string(index=False))

    assert len(violations) == 2
    assert set(violations["source_row"]) == {1, 2}
    assert set(violations["rule_id"]) == {"H01"}

    print("\nH01 test: PASS")


if __name__ == "__main__":
    main()