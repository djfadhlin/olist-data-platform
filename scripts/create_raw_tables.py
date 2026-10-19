
"""Buat sembilan tabel PostgreSQL raw dari shared schema.

DDL dieksekusi dalam satu transaksi.
Jika terjadi error, transaksi akan di-rollback.
"""

import os

import psycopg
from dotenv import load_dotenv

from olist.postgres import build_raw_ddl
from olist.schema import TABLE_SCHEMAS


def main():
    print("=== CREATE POSTGRES RAW TABLES ===")

    load_dotenv()

    connection_params = {
        "host": "localhost",
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.environ["POSTGRES_DB"],
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
    }

    ddl = build_raw_ddl()

    # Seluruh CREATE TABLE dijalankan dalam satu transaksi.
    with psycopg.connect(**connection_params) as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)

            # Verifikasi keberadaan sembilan tabel.
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'raw'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)

            existing_tables = {
                row[0] for row in cur.fetchall()
            }

            expected_tables = set(TABLE_SCHEMAS)

            missing = expected_tables - existing_tables

            if missing:
                raise RuntimeError(
                    f"Missing raw tables: {sorted(missing)}"
                )

            print("\n=== RAW TABLES ===")

            for table_name in sorted(expected_tables):
                print(f"PASS: raw.{table_name}")

            print(f"\nVerified tables: {len(expected_tables)}")

        # psycopg melakukan COMMIT saat keluar dari blok
        # koneksi tanpa exception.

    print("\nPostgreSQL raw DDL execution: PASS")


if __name__ == "__main__":
    main()
