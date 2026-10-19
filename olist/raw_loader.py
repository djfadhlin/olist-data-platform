
"""Loader Silver Parquet ke PostgreSQL schema raw.

Menggunakan COPY dalam satu transaksi untuk 9 tabel.
Tidak membuat koneksi sendiri: transaksi dikendalikan caller.
"""

from pathlib import Path
from time import perf_counter

import pyarrow.parquet as pq
from psycopg import sql

from olist.postgres import verify_raw_schema
from olist.schema import TABLE_SCHEMAS


BATCH_SIZE = 10000


def validate_silver_files(silver_dir: Path) -> dict:
    """Periksa seluruh Parquet sebelum database dimodifikasi."""

    silver_dir = Path(silver_dir)
    metadata = {}

    for table_name, table_spec in TABLE_SCHEMAS.items():
        path = silver_dir / f"{table_name}.parquet"

        if not path.is_file():
            raise FileNotFoundError(
                f"Silver Parquet tidak ditemukan: {path}"
            )

        parquet = pq.ParquetFile(path)

        actual_columns = parquet.schema_arrow.names
        expected_columns = [
            column.name for column in table_spec.columns
        ]

        if actual_columns != expected_columns:
            raise ValueError(
                f"Schema Parquet tidak sesuai: {table_name}\n"
                f"Expected: {expected_columns}\n"
                f"Actual: {actual_columns}"
            )

        metadata[table_name] = {
            "path": path,
            "rows": parquet.metadata.num_rows,
        }

    return metadata


def load_raw(conn, silver_dir: Path) -> dict:
    """TRUNCATE + COPY seluruh tabel dalam transaksi caller.

    Penting:
    Gunakan psycopg.connect(...) sebagai context manager.
    Context manager akan COMMIT jika sukses dan ROLLBACK
    jika terjadi exception.
    """

    start = perf_counter()

    # Validasi file dan struktur database SEBELUM TRUNCATE.
    metadata = validate_silver_files(silver_dir)
    verify_raw_schema(conn)

    table_names = list(TABLE_SCHEMAS)
    loaded_rows = {}

    with conn.cursor() as cur:

        # TRUNCATE semua tabel dalam transaksi yang sama.
        table_identifiers = [
            sql.Identifier("raw", name)
            for name in table_names
        ]

        truncate_query = sql.SQL("TRUNCATE TABLE {}").format(
            sql.SQL(", ").join(table_identifiers)
        )

        cur.execute(truncate_query)

        for table_name in table_names:
            table_spec = TABLE_SCHEMAS[table_name]
            parquet_path = metadata[table_name]["path"]

            columns = [
                column.name
                for column in table_spec.columns
            ]

            copy_query = sql.SQL(
                "COPY {} ({}) FROM STDIN"
            ).format(
                sql.Identifier("raw", table_name),
                sql.SQL(", ").join(
                    sql.Identifier(column)
                    for column in columns
                ),
            )

            parquet = pq.ParquetFile(parquet_path)
            inserted = 0

            with cur.copy(copy_query) as copy:
                for batch in parquet.iter_batches(
                    batch_size=BATCH_SIZE
                ):
                    # Arrow -> Python:
                    # NUMERIC -> Decimal
                    # TIMESTAMP -> datetime
                    # NULL -> None
                    records = batch.to_pylist()

                    for record in records:
                        row = tuple(
                            record[column]
                            for column in columns
                        )
                        copy.write_row(row)
                        inserted += 1

            expected = metadata[table_name]["rows"]

            if inserted != expected:
                raise RuntimeError(
                    f"{table_name}: COPY inserted {inserted}, "
                    f"expected {expected}"
                )

            cur.execute(
                sql.SQL("SELECT COUNT(*) FROM {}").format(
                    sql.Identifier("raw", table_name)
                )
            )

            database_rows = cur.fetchone()[0]

            if database_rows != expected:
                raise RuntimeError(
                    f"{table_name}: PostgreSQL has "
                    f"{database_rows} rows, expected {expected}"
                )

            loaded_rows[table_name] = database_rows

            print(
                f"PASS: raw.{table_name} "
                f"({database_rows:,} rows)"
            )

    elapsed = perf_counter() - start

    return {
        "tables": loaded_rows,
        "total_rows": sum(loaded_rows.values()),
        "duration_seconds": elapsed,
    }
