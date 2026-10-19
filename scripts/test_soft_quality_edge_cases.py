
from decimal import Decimal

import pandas as pd

from olist.soft_quality import check_cross_table_soft_rules


def main():
    print("=== SOFT QUALITY EDGE CASES ===")

    orders = pd.DataFrame({
        "order_id": ["o1", "o2", "o3", "o4"],
    })

    items = pd.DataFrame({
        "order_id": ["o1", "o2", "o3", "o4"],
        "price": ["100.00", "100.00", "100.00", "100.00"],
        "freight_value": ["10.00", "10.00", "10.00", "10.00"],
    })

    payments = pd.DataFrame({
        "order_id": ["o1", "o2", "o3"],
        "payment_value": [
            "110.00",  # Tepat sama
            "110.01",  # Selisih 0.01: masih toleransi
            "110.02",  # Selisih 0.02: S08
        ],
    })

    reviews = pd.DataFrame({
        "order_id": [],
        "review_id": [],
    })

    violations = check_cross_table_soft_rules(
        orders, items, payments, reviews
    )

    print(violations.to_string(index=False))

    s07_rows = set(
        violations.loc[
            violations["rule_id"] == "S07", "source_row"
        ]
    )

    s08_rows = set(
        violations.loc[
            violations["rule_id"] == "S08", "source_row"
        ]
    )

    # o4 tidak memiliki pembayaran.
    assert s07_rows == {3}

    # Hanya o3 melampaui toleransi BRL 0.01.
    assert s08_rows == {2}

    # o1 dan o2 tidak boleh terkena S08.
    assert 0 not in s08_rows
    assert 1 not in s08_rows

    print("\nS07 missing payments: PASS")
    print("S08 tolerance BRL 0.01: PASS")
    print("Soft quality edge cases: PASS")


if __name__ == "__main__":
    main()
