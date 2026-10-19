
"""Soft quality rules: flag, bukan karantina."""

import pandas as pd

from olist.silver import parse_timestamp


SOFT_COLUMNS = [
    "source_row",
    "column",
    "rule_id",
    "reason",
]


def check_orders_soft_rules(source: pd.DataFrame) -> pd.DataFrame:
    """Jalankan S01, S02, S03 pada Orders."""

    purchase = parse_timestamp(source["order_purchase_timestamp"])
    approved = parse_timestamp(source["order_approved_at"])
    carrier = parse_timestamp(source["order_delivered_carrier_date"])
    customer = parse_timestamp(source["order_delivered_customer_date"])

    status = source["order_status"].astype("string").str.strip()

    s01 = status.eq("delivered").fillna(False) & customer.isna()

    s02 = (
        carrier.notna()
        & customer.notna()
        & (customer < carrier).fillna(False)
    )

    s03 = (
        purchase.notna()
        & approved.notna()
        & (approved < purchase).fillna(False)
    )

    results = []

    rules = [
        ("S01", "order_delivered_customer_date", s01,
         "delivered_order_missing_customer_date"),
        ("S02", "order_delivered_customer_date", s02,
         "customer_delivery_before_carrier"),
        ("S03", "order_approved_at", s03,
         "approval_before_purchase"),
    ]

    for rule_id, column, mask, reason in rules:
        for idx in source.index[mask]:
            results.append({
                "source_row": idx,
                "column": column,
                "rule_id": rule_id,
                "reason": reason,
            })

    return pd.DataFrame(results, columns=SOFT_COLUMNS)


def check_geolocation_soft_rules(source: pd.DataFrame) -> pd.DataFrame:
    """S04: Flag koordinat di luar rentang wajar Brasil."""

    latitude = pd.to_numeric(
        source["geolocation_lat"], errors="coerce"
    )
    longitude = pd.to_numeric(
        source["geolocation_lng"], errors="coerce"
    )

    invalid = (
        (latitude.notna() & ~latitude.between(-34, 5))
        | (longitude.notna() & ~longitude.between(-74, -35))
    )

    results = []

    for idx in source.index[invalid]:
        results.append({
            "source_row": idx,
            "column": "geolocation_lat,geolocation_lng",
            "rule_id": "S04",
            "reason": "geolocation_outside_brazil_range",
        })

    return pd.DataFrame(results, columns=SOFT_COLUMNS)

from decimal import Decimal

from olist.silver import parse_money


def check_cross_table_soft_rules(
    orders: pd.DataFrame,
    items: pd.DataFrame,
    payments: pd.DataFrame,
    reviews: pd.DataFrame,
) -> pd.DataFrame:
    """S05-S08: pemeriksaan kualitas lintas tabel.

    Sumber diasumsikan sudah lolos hard quality gate.
    source_row untuk S05-S08 merujuk indeks tabel Orders.
    """

    results = []

    order_ids = orders["order_id"].astype("string").str.strip()
    item_order_ids = set(items["order_id"].dropna().astype(str))
    payment_order_ids = set(payments["order_id"].dropna().astype(str))

    review_counts = reviews.groupby("order_id").size()
    repeated_reviews = set(
        review_counts[review_counts > 1].index.astype(str)
    )

    def add_flag(idx, rule_id, column, reason):
        results.append({
            "source_row": idx,
            "column": column,
            "rule_id": rule_id,
            "reason": reason,
        })

    for idx, order_id in order_ids.items():
        if pd.isna(order_id) or not order_id:
            continue

        if order_id in repeated_reviews:
            add_flag(
                idx, "S05", "order_id",
                "multiple_reviews_per_order"
            )

        if order_id not in item_order_ids:
            add_flag(
                idx, "S06", "order_id",
                "order_without_items"
            )

        if order_id not in payment_order_ids:
            add_flag(
                idx, "S07", "order_id",
                "order_without_payments"
            )

    # Hitung nominal items dan payments secara presisi.
    item_totals = {}
    for row in items.itertuples(index=False):
        price = parse_money(pd.Series([row.price])).iloc[0]
        freight = parse_money(pd.Series([row.freight_value])).iloc[0]

        if price is None or freight is None:
            continue

        key = str(row.order_id)
        item_totals[key] = (
            item_totals.get(key, Decimal("0.00"))
            + price
            + freight
        )

    payment_totals = {}
    for row in payments.itertuples(index=False):
        value = parse_money(
            pd.Series([row.payment_value])
        ).iloc[0]

        if value is None:
            continue

        key = str(row.order_id)
        payment_totals[key] = (
            payment_totals.get(key, Decimal("0.00"))
            + value
        )

    tolerance = Decimal("0.01")

    for idx, order_id in order_ids.items():
        if pd.isna(order_id):
            continue

        # Bandingkan hanya order yang memiliki kedua sisi.
        if order_id not in item_totals or order_id not in payment_totals:
            continue

        difference = abs(
            item_totals[order_id] - payment_totals[order_id]
        )

        if difference > tolerance:
            add_flag(
                idx, "S08", "order_id",
                "payment_amount_mismatch"
            )

    return pd.DataFrame(results, columns=SOFT_COLUMNS)


def run_all_soft_rules(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Gabungkan hasil S01-S08 untuk dataset yang tersedia.

    Hasil memiliki source_table agar setiap flag dapat
    ditelusuri ke tabel asalnya.
    """
    results = []

    orders_name = "olist_orders_dataset"
    geo_name = "olist_geolocation_dataset"

    if orders_name in tables:
        orders_flags = check_orders_soft_rules(tables[orders_name]).copy()

        if not orders_flags.empty:
            orders_flags["source_table"] = orders_name
            results.append(orders_flags)

    if geo_name in tables:
        geo_flags = check_geolocation_soft_rules(tables[geo_name]).copy()

        if not geo_flags.empty:
            geo_flags["source_table"] = geo_name
            results.append(geo_flags)

    cross_table_names = {
        "olist_orders_dataset",
        "olist_order_items_dataset",
        "olist_order_payments_dataset",
        "olist_order_reviews_dataset",
    }

    if cross_table_names.issubset(tables):
        cross_flags = check_cross_table_soft_rules(
            orders=tables["olist_orders_dataset"],
            items=tables["olist_order_items_dataset"],
            payments=tables["olist_order_payments_dataset"],
            reviews=tables["olist_order_reviews_dataset"],
        ).copy()

        if not cross_flags.empty:
            cross_flags["source_table"] = orders_name
            results.append(cross_flags)

    columns = [
        "source_table",
        "source_row",
        "column",
        "rule_id",
        "reason",
    ]

    if not results:
        return pd.DataFrame(columns=columns)

    return pd.concat(results, ignore_index=True)[columns]
