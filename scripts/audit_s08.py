
"""Audit hasil S08 berdasarkan total items dan payments."""

from decimal import Decimal
from pathlib import Path

import pandas as pd


RAW_DIR = Path("data/raw")


def to_decimal(value):
    return Decimal(str(value))


def main():
    print("=== S08 PAYMENT RECONCILIATION AUDIT ===")

    items = pd.read_csv(
        RAW_DIR / "olist_order_items_dataset.csv",
        dtype="string",
        keep_default_na=False,
    )

    payments = pd.read_csv(
        RAW_DIR / "olist_order_payments_dataset.csv",
        dtype="string",
        keep_default_na=False,
    )

    orders = pd.read_csv(
        RAW_DIR / "olist_orders_dataset.csv",
        dtype="string",
        keep_default_na=False,
    )

    item_totals = {}

    for row in items.itertuples(index=False):
        order_id = row.order_id
        amount = (
            to_decimal(row.price)
            + to_decimal(row.freight_value)
        )
        item_totals[order_id] = (
            item_totals.get(order_id, Decimal("0.00"))
            + amount
        )

    payment_totals = {}

    for row in payments.itertuples(index=False):
        order_id = row.order_id
        amount = to_decimal(row.payment_value)
        payment_totals[order_id] = (
            payment_totals.get(order_id, Decimal("0.00"))
            + amount
        )

    all_orders = set(orders["order_id"])

    common_orders = (
        all_orders
        & set(item_totals)
        & set(payment_totals)
    )

    mismatch = {
        order_id: abs(
            item_totals[order_id] - payment_totals[order_id]
        )
        for order_id in common_orders
        if abs(
            item_totals[order_id] - payment_totals[order_id]
        ) > Decimal("0.01")
    }

    print("Total orders:", len(all_orders))
    print("Orders with both items and payments:", len(common_orders))
    print("Orders with payment mismatch > 0.01:", len(mismatch))

    print("\nTop 5 largest differences:")
    for order_id, diff in sorted(
        mismatch.items(),
        key=lambda pair: pair[1],
        reverse=True,
    )[:5]:
        print(f"{order_id}: BRL {diff}")

    print("\nS08 audit: COMPLETE")


if __name__ == "__main__":
    main()
