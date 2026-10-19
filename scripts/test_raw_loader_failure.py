
"""Failure injection COPY dan verifikasi rollback PostgreSQL."""

import os
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd
import psycopg
from dotenv import load_dotenv

from olist.raw_loader import load_raw
from olist.schema import TABLE_SCHEMAS


TABLE = "olist_order_payments_dataset"


def connect():
    load_dotenv()

    return psycopg.connect(
        host="localhost",
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def get_rows():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT order_id, payment_value '
                'FROM raw."olist_order_payments_dataset" '
                'ORDER BY order_id, payment_sequential'
            )
            return cur.fetchall()


def main():
    print("=== RAW LOADER FAILURE INJECTION TEST ===")

    before = get_rows()
    print("Rows before:", len(before))

    # Data sintetis sengaja melanggar NUMERIC(12,2).
    # Tidak melewati parser Silver karena ini khusus
    # pengujian kegagalan di lapisan PostgreSQL.
    source = pd.DataFrame({
        "order_id": ["order_test_001", "order_test_002"],
        "payment_sequential": [1, 1],
        "payment_type": ["credit_card", "boleto"],
        "payment_installments": [1, 1],
        "payment_value": [
            Decimal("100.00"),
            Decimal("10000000000.00"),
        ],
    })

    with TemporaryDirectory() as temp_dir:
        silver_dir = Path(temp_dir)

        source.to_parquet(
            silver_dir / f"{TABLE}.parquet",
            engine="pyarrow",
            index=False,
        )

        failed_as_expected = False

        # Jangan gunakan with psycopg.connect(...) di sini
        # untuk kasus ketika exception tertangkap.
        # Kita mengendalikan rollback secara eksplisit.
        conn = connect()

        try:
            with patch(
                "olist.raw_loader.TABLE_SCHEMAS",
                {TABLE: TABLE_SCHEMAS[TABLE]},
            ):
                try:
                    load_raw(conn, silver_dir)
                except psycopg.errors.NumericValueOutOfRange:
                    failed_as_expected = True
                    print("Injected numeric overflow: detected")
                finally:
                    # WAJIB rollback, baik COPY gagal maupun sukses.
                    conn.rollback()
        finally:
            conn.close()

        assert failed_as_expected, (
            "Expected PostgreSQL numeric overflow was not raised"
        )

    after = get_rows()

    print("Rows after:", len(after))

    assert after == before, (
        "Database contents changed after failed COPY"
    )

    print("Database contents preserved: PASS")
    print("Automatic transaction rollback: PASS")
    print("\nRaw loader failure injection test: PASS")


if __name__ == "__main__":
    main()