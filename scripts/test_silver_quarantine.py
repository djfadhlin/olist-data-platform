import pandas as pd

from olist.silver import (
    parse_table,
    detect_parse_failures,
    quarantine_parse_failures,
)


def main():
    print("=== SILVER QUARANTINE TEST ===")

    source = pd.DataFrame({
        "order_id": ["order_001", "order_002", "order_003"],
        "payment_sequential": ["1", "2.5", "3"],
        "payment_type": ["credit_card", "voucher", "boleto"],
        "payment_installments": ["3", "1", "1"],
        "payment_value": ["125.50", "ABC", "50.00"],
    })

    parsed = parse_table(source, "olist_order_payments_dataset")

    failures = detect_parse_failures(
        source,
        parsed,
        "olist_order_payments_dataset",
    )

    silver, quarantine = quarantine_parse_failures(
        source,
        parsed,
        failures,
        "olist_order_payments_dataset",
    )

    print("Source rows:", len(source))
    print("Parse violations:", len(failures))
    print("Silver rows:", len(silver))
    print("Quarantine rows:", len(quarantine))

    print("\n=== QUARANTINE DETAILS ===")
    print(quarantine[["order_id", "source_row", "reason"]].to_string(index=False))

    assert len(source) == 3
    assert len(failures) == 2
    assert len(silver) == 2
    assert len(quarantine) == 1

    assert quarantine.iloc[0]["order_id"] == "order_002"
    assert quarantine.iloc[0]["payment_value"] == "ABC"

    reason = quarantine.iloc[0]["reason"]

    assert "payment_sequential" in reason
    assert "payment_value" in reason

    assert len(source) == len(silver) + len(quarantine)

    print("\nQuarantine test: PASS")

if __name__ == "__main__":
    main()