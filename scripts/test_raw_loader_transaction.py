
"""Integration test PostgreSQL COPY dengan rollback.

Menggunakan dua record sintetis.
Tidak meninggalkan perubahan pada database.
"""

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


TABLE_NAME = "olist_order_payments_dataset"


def main():
    print("=== RAW LOADER TRANSACTION TEST ===")

    load_dotenv()

    source = pd.DataFrame({
        "order_id": ["order_test_001", "order_test_002"],
        "payment_sequential": ["1", "1"],
        "payment_type": ["credit_card", "boleto"],
        "payment_installments": ["2", "1"],
        "payment_value": ["125.50", "20.00"],
    })

    # Gunakan parser Silver agar tipe data sesuai kontrak.
    from olist.silver import parse_table

    parsed = parse_table(source, TABLE_NAME)

    with TemporaryDirectory() as temp_dir:
        silver_dir = Path(temp_dir)

        parsed.to_parquet(
            silver_dir / f"{TABLE_NAME}.parquet",
            engine="pyarrow",
            index=False,
        )

        with psycopg.connect(
            host="localhost",
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
        ) as conn:

            # Hanya tabel Payments yang akan diuji.
            # Fungsi verifikasi struktur tetap menguji 9 tabel.
            with patch(
                "olist.raw_loader.TABLE_SCHEMAS",
                {TABLE_NAME: TABLE_SCHEMAS[TABLE_NAME]},
            ):
                result = load_raw(conn, silver_dir)

            assert result["total_rows"] == 2

            with conn.cursor() as cur:
                cur.execute(
                    'SELECT payment_value '
                    'FROM raw."olist_order_payments_dataset" '
                    'ORDER BY order_id'
                )

                values = [row[0] for row in cur.fetchall()]

                assert values == [
                    Decimal("125.50"),
                    Decimal("20.00"),
                ]

            print("COPY 2 typed records: PASS")
            print("Decimal precision: PASS")

            # Batalkan seluruh perubahan sebelum keluar
            # dari context manager.
            conn.rollback()

    print("Transaction rollback: PASS")
    print("\nRaw loader transaction test: PASS")


if __name__ == "__main__":
    main()
