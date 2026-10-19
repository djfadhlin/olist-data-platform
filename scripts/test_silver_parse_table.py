from decimal import Decimal

import pandas as pd

from olist.silver import parse_table


def main():
    print("=== SILVER PARSE TABLE TEST ===")

    source = pd.DataFrame({
        "order_id": ["order_001", "order_002"],
        "payment_sequential": ["1", "2"],
        "payment_type": ["credit_card", "voucher"],
        "payment_installments": ["3", "1"],
        "payment_value": ["125.50", "ABC"],
    })

    parsed = parse_table(
        source,
        "olist_order_payments_dataset",
    )

    print(parsed.dtypes)

    assert str(parsed["payment_sequential"].dtype) == "Int64"
    assert str(parsed["payment_installments"].dtype) == "Int64"

    assert parsed["payment_value"].iloc[0] == Decimal("125.50")
    assert pd.isna(parsed["payment_value"].iloc[1])

    assert parsed["order_id"].iloc[0] == "order_001"

    print("\nParse table test: PASS")


if __name__ == "__main__":
    main()