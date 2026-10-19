
"""Pengujian round-trip Parquet untuk tipe data Silver."""

from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from olist.silver import parse_table


def main():
    print("=== SILVER PARQUET ROUND-TRIP TEST ===")

    source = pd.DataFrame({
        "order_id": ["order_001", "order_002"],
        "payment_sequential": ["1", "2"],
        "payment_type": ["credit_card", "boleto"],
        "payment_installments": ["3", "1"],
        "payment_value": ["125.50", "20.00"],
    })

    silver = parse_table(
        source,
        "olist_order_payments_dataset",
    )

    with TemporaryDirectory() as temp_dir:
        parquet_path = Path(temp_dir) / "payments.parquet"

        silver.to_parquet(
            parquet_path,
            engine="pyarrow",
            index=False,
        )

        restored = pd.read_parquet(
            parquet_path,
            engine="pyarrow",
        )

        print("Rows written:", len(silver))
        print("Rows restored:", len(restored))
        print("Columns:", list(restored.columns))
        print("Payment value:", restored.loc[0, "payment_value"])
        print("Payment value type:",
              type(restored.loc[0, "payment_value"]).__name__)

        assert len(restored) == len(silver)
        assert list(restored.columns) == list(silver.columns)

        assert restored.loc[0, "payment_value"] == Decimal("125.50")
        assert restored.loc[1, "payment_value"] == Decimal("20.00")

        assert restored.loc[0, "order_id"] == "order_001"
        assert restored.loc[0, "payment_sequential"] == 1

        print("\nSilver Parquet round-trip: PASS")


if __name__ == "__main__":
    main()
