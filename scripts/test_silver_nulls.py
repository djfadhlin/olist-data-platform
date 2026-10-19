import pandas as pd

from olist.silver import parse_table, detect_null_violations


def main():
    print("=== NOT NULL VALIDATION TEST ===")

    source = pd.DataFrame({
        "order_id": ["order_001", "", "order_003"],
        "payment_sequential": ["1", "2", "3"],
        "payment_type": ["credit_card", "voucher", "boleto"],
        "payment_installments": ["3", "1", "1"],
        "payment_value": ["125.50", "20.00", None],
    })

    parsed = parse_table(
        source,
        "olist_order_payments_dataset",
    )

    violations = detect_null_violations(
        source,
        parsed,
        "olist_order_payments_dataset",
    )

    print(violations.to_string(index=False))

    assert len(violations) == 2
    assert set(violations["column"]) == {
        "order_id",
        "payment_value",
    }

    assert set(violations["source_row"]) == {1, 2}

    print("\nNOT NULL validation test: PASS")


if __name__ == "__main__":
    main()