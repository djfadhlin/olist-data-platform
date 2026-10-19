import pandas as pd

from olist.silver import parse_table, detect_parse_failures


def main():
    print("=== PARSE FAILURE DETECTION TEST ===")

    source = pd.DataFrame({
        "order_id": ["order_001", "order_002", "order_003"],
        "payment_sequential": ["1", "2.5", "3"],
        "payment_type": ["credit_card", "voucher", "boleto"],
        "payment_installments": ["3", "1", "1"],
        "payment_value": ["125.50", "ABC", ""],
    })

    parsed = parse_table(
        source,
        "olist_order_payments_dataset",
    )

    failures = detect_parse_failures(
        source,
        parsed,
        "olist_order_payments_dataset",
    )

    print(failures.to_string(index=False))

    assert len(failures) == 2

    assert set(failures["column"]) == {
        "payment_sequential",
        "payment_value",
    }

    assert set(failures["original_value"]) == {
        "2.5",
        "ABC",
    }

    print("\nParse failure detection test: PASS")


if __name__ == "__main__":
    main()