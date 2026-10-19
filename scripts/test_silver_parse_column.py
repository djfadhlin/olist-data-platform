from decimal import Decimal

import pandas as pd

from olist.schema import ColumnSpec
from olist.silver import parse_column


def main():
    print("=== SILVER PARSE COLUMN TEST ===")

    # 1. NUMERIC(12,2)
    money_column = ColumnSpec(
        "payment_value", "NUMERIC(12,2)", False
    )

    money = parse_column(
        pd.Series(["125.50", "ABC"], dtype="string"),
        money_column,
    )

    assert money.iloc[0] == Decimal("125.50")
    assert pd.isna(money.iloc[1])
    print("Money parser: PASS")

    # 2. TIMESTAMP
    timestamp_column = ColumnSpec(
        "order_purchase_timestamp", "TIMESTAMP", False
    )

    timestamps = parse_column(
        pd.Series(
            ["2018-01-15 13:45:00", "bukan-tanggal"],
            dtype="string",
        ),
        timestamp_column,
    )

    assert timestamps.iloc[0] == pd.Timestamp(
        "2018-01-15 13:45:00"
    )
    assert pd.isna(timestamps.iloc[1])
    print("Timestamp parser: PASS")

    # 3. ZIP PREFIX
    zip_column = ColumnSpec(
        "customer_zip_code_prefix", "VARCHAR(5)", False
    )

    zip_codes = parse_column(
        pd.Series(["01310", "1234"], dtype="string"),
        zip_column,
    )

    assert zip_codes.iloc[0] == "01310"
    assert pd.isna(zip_codes.iloc[1])
    print("ZIP parser: PASS")

    print("\nAll parse_column tests: PASS")


if __name__ == "__main__":
    main()