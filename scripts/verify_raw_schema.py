
"""Verifikasi struktur sembilan tabel PostgreSQL raw."""

import os

import psycopg
from dotenv import load_dotenv

from olist.postgres import verify_raw_schema
from olist.schema import TABLE_SCHEMAS


def main():
    print("=== VERIFY POSTGRES RAW SCHEMA ===")

    # Baca konfigurasi PostgreSQL dari .env.
    load_dotenv()

    connection_params = {
        "host": "localhost",
        "port": int(
            os.getenv("POSTGRES_PORT", "5432")
        ),
        "dbname": os.environ["POSTGRES_DB"],
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
    }

    # Buka koneksi PostgreSQL.
    with psycopg.connect(**connection_params) as conn:

        # Verifikasi seluruh struktur tabel raw.
        verify_raw_schema(conn)

    print(
        f"Verified tables: {len(TABLE_SCHEMAS)}"
    )

    print(
        "Column names, order, types, NOT NULL: PASS"
    )

    print(
        "\nPostgreSQL raw schema verification: PASS"
    )


if __name__ == "__main__":
    main()
