
"""PostgreSQL DDL dan verifikasi struktur tabel raw Olist.

Menggunakan satu sumber definisi tabel dari olist/schema.py.
"""

from olist.schema import TABLE_SCHEMAS


def build_raw_ddl() -> str:
    """Bangun DDL PostgreSQL dari shared schema.py."""

    statements = [
        "CREATE SCHEMA IF NOT EXISTS raw;"
    ]

    for table_name, table_spec in TABLE_SCHEMAS.items():
        columns = []

        for column in table_spec.columns:
            nullable = "" if column.nullable else " NOT NULL"

            columns.append(
                f'    "{column.name}" {column.pg_type}{nullable}'
            )

        column_sql = ",\n".join(columns)

        statement = (
            f'CREATE TABLE IF NOT EXISTS raw."{table_name}" (\n'
            f"{column_sql}\n"
            ");"
        )

        statements.append(statement)

    return "\n\n".join(statements) + "\n"


def verify_raw_schema(conn) -> None:
    """Pastikan struktur PostgreSQL raw sesuai shared schema.

    Validasi mencakup:
    - Jumlah kolom
    - Nama kolom
    - Urutan kolom
    - Tipe PostgreSQL
    - Panjang VARCHAR
    - Presisi dan skala NUMERIC
    - NULL / NOT NULL

    Fungsi ini hanya membaca metadata.
    Tidak mengubah tabel atau data.
    """

    with conn.cursor() as cur:

        for table_name, table_spec in TABLE_SCHEMAS.items():

            cur.execute(
                """
                SELECT
                    column_name,
                    udt_name,
                    is_nullable,
                    character_maximum_length,
                    numeric_precision,
                    numeric_scale
                FROM information_schema.columns
                WHERE table_schema = 'raw'
                  AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table_name,),
            )

            actual_columns = cur.fetchall()
            expected_columns = list(table_spec.columns)

            # ==========================================
            # VALIDASI JUMLAH KOLOM
            # ==========================================

            if len(actual_columns) != len(expected_columns):
                raise ValueError(
                    f"{table_name}: expected "
                    f"{len(expected_columns)} columns, "
                    f"found {len(actual_columns)}"
                )

            # ==========================================
            # VALIDASI SETIAP KOLOM
            # ==========================================

            for actual_col, expected_col in zip(
                actual_columns,
                expected_columns,
            ):
                (
                    name,
                    udt_name,
                    is_nullable,
                    max_length,
                    precision,
                    scale,
                ) = actual_col

                # Nama dan urutan kolom.
                if name != expected_col.name:
                    raise ValueError(
                        f"{table_name}: column mismatch, "
                        f"expected {expected_col.name}, "
                        f"found {name}"
                    )

                pg_type = expected_col.pg_type.upper()

                # ======================================
                # VALIDASI TIPE DATA
                # ======================================

                if pg_type == "INTEGER":
                    type_ok = udt_name == "int4"

                elif pg_type == "TIMESTAMP":
                    type_ok = udt_name == "timestamp"

                elif pg_type == "DOUBLE PRECISION":
                    type_ok = udt_name == "float8"

                elif pg_type == "TEXT":
                    type_ok = udt_name == "text"

                elif pg_type.startswith("VARCHAR("):

                    expected_length = int(
                        pg_type.removeprefix(
                            "VARCHAR("
                        ).rstrip(")")
                    )

                    type_ok = (
                        udt_name == "varchar"
                        and max_length == expected_length
                    )

                elif pg_type.startswith("NUMERIC("):

                    numeric_spec = pg_type.removeprefix(
                        "NUMERIC("
                    ).rstrip(")")

                    (
                        expected_precision,
                        expected_scale,
                    ) = map(
                        int,
                        numeric_spec.split(","),
                    )

                    type_ok = (
                        udt_name == "numeric"
                        and precision == expected_precision
                        and scale == expected_scale
                    )

                else:
                    raise ValueError(
                        f"Unsupported PostgreSQL type: "
                        f"{pg_type}"
                    )

                if not type_ok:
                    raise ValueError(
                        f"{table_name}.{name}: PostgreSQL "
                        f"type mismatch. Expected {pg_type}, "
                        f"found {udt_name}"
                    )

                # ======================================
                # VALIDASI NULL / NOT NULL
                # ======================================

                expected_nullable = (
                    "YES"
                    if expected_col.nullable
                    else "NO"
                )

                if is_nullable != expected_nullable:
                    raise ValueError(
                        f"{table_name}.{name}: nullable "
                        f"mismatch. Expected "
                        f"{expected_nullable}, "
                        f"found {is_nullable}"
                    )
