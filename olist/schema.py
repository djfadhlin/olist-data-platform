"""Definisi terpusat skema data Olist.

Acuan: DATA_CONTRACT.md, bagian 3 dan 4.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    pg_type: str
    nullable: bool


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[ColumnSpec, ...]
    natural_key: tuple[str, ...]


TABLE_SCHEMAS: dict[str, TableSpec] = {
    "olist_customers_dataset": TableSpec(
        name="olist_customers_dataset",
        columns=(
            ColumnSpec("customer_id", "VARCHAR(32)", False),
            ColumnSpec("customer_unique_id", "VARCHAR(32)", False),
            ColumnSpec("customer_zip_code_prefix", "VARCHAR(5)", False),
            ColumnSpec("customer_city", "TEXT", False),
            ColumnSpec("customer_state", "VARCHAR(2)", False),
        ),
        natural_key=("customer_id",),
    ),

     "olist_geolocation_dataset": TableSpec(
        name="olist_geolocation_dataset",
        columns=(
            ColumnSpec("geolocation_zip_code_prefix", "VARCHAR(5)", False),
            ColumnSpec("geolocation_lat", "DOUBLE PRECISION", False),
            ColumnSpec("geolocation_lng", "DOUBLE PRECISION", False),
            ColumnSpec("geolocation_city", "TEXT", False),
            ColumnSpec("geolocation_state", "VARCHAR(2)", False),
        ),
        natural_key=(),
    ),

        "olist_order_items_dataset": TableSpec(
        name="olist_order_items_dataset",
        columns=(
            ColumnSpec("order_id", "VARCHAR(32)", False),
            ColumnSpec("order_item_id", "INTEGER", False),
            ColumnSpec("product_id", "VARCHAR(32)", False),
            ColumnSpec("seller_id", "VARCHAR(32)", False),
            ColumnSpec("shipping_limit_date", "TIMESTAMP", False),
            ColumnSpec("price", "NUMERIC(12,2)", False),
            ColumnSpec("freight_value", "NUMERIC(12,2)", False),
        ),
        natural_key=("order_id", "order_item_id"),
    ),

        "olist_order_payments_dataset": TableSpec(
        name="olist_order_payments_dataset",
        columns=(
            ColumnSpec("order_id", "VARCHAR(32)", False),
            ColumnSpec("payment_sequential", "INTEGER", False),
            ColumnSpec("payment_type", "TEXT", False),
            ColumnSpec("payment_installments", "INTEGER", False),
            ColumnSpec("payment_value", "NUMERIC(12,2)", False),
        ),
        natural_key=("order_id", "payment_sequential"),
    ),

        "olist_order_reviews_dataset": TableSpec(
        name="olist_order_reviews_dataset",
        columns=(
            ColumnSpec("review_id", "VARCHAR(32)", False),
            ColumnSpec("order_id", "VARCHAR(32)", False),
            ColumnSpec("review_score", "INTEGER", False),
            ColumnSpec("review_comment_title", "TEXT", True),
            ColumnSpec("review_comment_message", "TEXT", True),
            ColumnSpec("review_creation_date", "TIMESTAMP", False),
            ColumnSpec("review_answer_timestamp", "TIMESTAMP", False),
        ),
        natural_key=("review_id", "order_id"),
    ),

        "olist_orders_dataset": TableSpec(
        name="olist_orders_dataset",
        columns=(
            ColumnSpec("order_id", "VARCHAR(32)", False),
            ColumnSpec("customer_id", "VARCHAR(32)", False),
            ColumnSpec("order_status", "TEXT", False),
            ColumnSpec("order_purchase_timestamp", "TIMESTAMP", False),
            ColumnSpec("order_approved_at", "TIMESTAMP", True),
            ColumnSpec("order_delivered_carrier_date", "TIMESTAMP", True),
            ColumnSpec("order_delivered_customer_date", "TIMESTAMP", True),
            ColumnSpec("order_estimated_delivery_date", "TIMESTAMP", False),
        ),
        natural_key=("order_id",),
    ),

        "olist_products_dataset": TableSpec(
        name="olist_products_dataset",
        columns=(
            ColumnSpec("product_id", "VARCHAR(32)", False),
            ColumnSpec("product_category_name", "TEXT", True),
            ColumnSpec("product_name_lenght", "INTEGER", True),
            ColumnSpec("product_description_lenght", "INTEGER", True),
            ColumnSpec("product_photos_qty", "INTEGER", True),
            ColumnSpec("product_weight_g", "INTEGER", True),
            ColumnSpec("product_length_cm", "INTEGER", True),
            ColumnSpec("product_height_cm", "INTEGER", True),
            ColumnSpec("product_width_cm", "INTEGER", True),
        ),
        natural_key=("product_id",),
    ),

        "olist_sellers_dataset": TableSpec(
        name="olist_sellers_dataset",
        columns=(
            ColumnSpec("seller_id", "VARCHAR(32)", False),
            ColumnSpec("seller_zip_code_prefix", "VARCHAR(5)", False),
            ColumnSpec("seller_city", "TEXT", False),
            ColumnSpec("seller_state", "VARCHAR(2)", False),
        ),
        natural_key=("seller_id",),
    ),

        "product_category_name_translation": TableSpec(
        name="product_category_name_translation",
        columns=(
            ColumnSpec("product_category_name", "TEXT", False),
            ColumnSpec("product_category_name_english", "TEXT", False),
        ),
        natural_key=("product_category_name",),
    ),
}

import csv
from pathlib import Path


def validate_csv_headers(raw_dir: Path) -> None:
    """Memastikan header CSV sesuai dengan kontrak skema."""

    for table_name, table_spec in TABLE_SCHEMAS.items():
        file_path = raw_dir / f"{table_name}.csv"

        if not file_path.is_file():
            raise FileNotFoundError(
                f"File sumber tidak ditemukan: {file_path.name}"
            )

        with file_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            reader = csv.reader(file)
            actual_columns = next(reader, [])

        expected_columns = [
            column.name
            for column in table_spec.columns
        ]

        missing = sorted(set(expected_columns) - set(actual_columns))
        unexpected = sorted(set(actual_columns) - set(expected_columns))

        if missing or unexpected or actual_columns != expected_columns:
            raise ValueError(
                f"Schema drift pada {file_path.name}: "
                f"missing={missing}, "
                f"unexpected={unexpected}, "
                f"expected_order={expected_columns}, "
                f"actual_order={actual_columns}"
            )

        print(f"{table_name}: PASS ({len(expected_columns)} columns)")