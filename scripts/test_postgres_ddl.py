
"""Unit test generator DDL raw PostgreSQL."""

from olist.postgres import build_raw_ddl
from olist.schema import TABLE_SCHEMAS


def main():
    print("=== POSTGRES RAW DDL TEST ===")

    ddl = build_raw_ddl()

    assert "CREATE SCHEMA IF NOT EXISTS raw;" in ddl

    # Setiap dataset harus memiliki CREATE TABLE.
    for table_name in TABLE_SCHEMAS:
        expected = (
            f'CREATE TABLE IF NOT EXISTS raw."{table_name}"'
        )
        assert expected in ddl, table_name

    # Validasi tipe kolom penting.
    assert '"order_purchase_timestamp" TIMESTAMP' in ddl
    assert '"payment_value" NUMERIC(12,2)' in ddl
    assert '"price" NUMERIC(12,2)' in ddl

    # ZIP harus bertipe teks, bukan INTEGER.
    assert '"customer_zip_code_prefix" VARCHAR(5)' in ddl

    assert ddl.count("CREATE TABLE IF NOT EXISTS") == 9

    print("Tables:", len(TABLE_SCHEMAS))
    print("DDL statements: 9 CREATE TABLE")
    print("TIMESTAMP: PASS")
    print("NUMERIC(12,2): PASS")
    print("ZIP VARCHAR(5): PASS")

    print("\nPostgres raw DDL test: PASS")


if __name__ == "__main__":
    main()
