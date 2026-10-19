import pandas as pd

from olist.silver import (
    parse_table,
    collect_basic_violations,
    quarantine_parse_failures,
)


def main():
    print("=== BASIC VIOLATIONS TEST ===")

    source = pd.DataFrame({
        "order_id": ["order_001", "", "order_003"],
        "payment_sequential": ["1", "2.5", "3"],
        "payment_type": ["credit_card", "voucher", "boleto"],
        "payment_installments": ["3", "1", "1"],
        "payment_value": ["125.50", "ABC", None],
    })

    parsed = parse_table(
        source,
        "olist_order_payments_dataset",
    )

    violations = collect_basic_violations(
        source,
        parsed,
        "olist_order_payments_dataset",
    )

    silver, quarantine = quarantine_parse_failures(
        source,
        parsed,
        violations,
        "olist_order_payments_dataset",
    )

    print("Source rows:", len(source))
    print("Violations:", len(violations))
    print("Silver rows:", len(silver))
    print("Quarantine rows:", len(quarantine))

    print("\n=== QUARANTINE DETAILS ===")
    print(
        quarantine[
            ["source_row", "order_id", "reason"]
        ].to_string(index=False)
    )

    assert len(source) == 3
    assert len(violations) == 4
    assert len(silver) == 1
    assert len(quarantine) == 2

    assert set(quarantine["source_row"]) == {1, 2}

    assert len(source) == len(silver) + len(quarantine)

    print("\nBasic violations test: PASS")


if __name__ == "__main__":
    main()