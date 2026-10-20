
"""Buat dan verifikasi tabel PostgreSQL stream."""

import os

import psycopg
from dotenv import load_dotenv

from olist.stream_db import (
    create_stream_schema,
    verify_stream_schema,
)


def main():
    load_dotenv()

    print("=== T3 CREATE STREAM TABLES ===")

    with psycopg.connect(
        host="localhost",
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as conn:
        create_stream_schema(conn)
        verify_stream_schema(conn)

    print("\nT3 PostgreSQL stream schema: PASS")


if __name__ == "__main__":
    main()
