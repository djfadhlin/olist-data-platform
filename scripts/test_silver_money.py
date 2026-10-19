from decimal import Decimal

import pandas as pd

from olist.silver import parse_money


def main():
    values = pd.Series(
        [
            "125.50",
            "0",
            "12.3",
            "-5.00",
            "12.345",
            "ABC",
            "10000000000.00",
            None,
        ],
        dtype="string",
    )

    result = parse_money(values)

    print("=== MONEY PARSING TEST ===")

    for original, parsed in zip(values, result):
        print(f"{original!r} -> {parsed!r}")

    assert result.iloc[0] == Decimal("125.50")
    assert result.iloc[1] == Decimal("0.00")
    assert result.iloc[2] == Decimal("12.30")
    assert result.iloc[3] == Decimal("-5.00")

    assert pd.isna(result.iloc[4])
    assert pd.isna(result.iloc[5])
    assert pd.isna(result.iloc[6])
    assert pd.isna(result.iloc[7])

    print("\nMoney parsing test: PASS")


if __name__ == "__main__":
    main()