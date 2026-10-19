"""Transformasi dan validasi data Silver Olist."""

from olist.schema import ColumnSpec, TABLE_SCHEMAS

from decimal import Decimal, InvalidOperation

import re

import pandas as pd


def parse_zip_prefix(series: pd.Series) -> pd.Series:
    """Mempertahankan kode pos sebagai teks lima digit.

    Nilai kosong atau format tidak valid dikembalikan sebagai pd.NA.
    """

    values = series.astype("string").str.strip()

    valid = values.str.fullmatch(r"[0-9]{5}").fillna(False)

    return values.where(valid, pd.NA)

def parse_integer(series: pd.Series) -> pd.Series:
    """Mengubah nilai menjadi integer nullable secara ketat."""

    values = series.astype("string").str.strip()

    # Hanya menerima bilangan bulat dengan tanda opsional.
    valid = values.str.fullmatch(r"[+-]?[0-9]+").fillna(False)

    numeric = pd.to_numeric(
        values.where(valid),
        errors="coerce",
    )

    # Gunakan tipe integer nullable pandas.
    return numeric.astype("Int64")

def parse_timestamp(series: pd.Series) -> pd.Series:
    """Parsing timestamp sesuai format kontrak Olist."""

    values = series.astype("string").str.strip()

    return pd.to_datetime(
        values,
        format="%Y-%m-%d %H:%M:%S",
        errors="coerce",
    )

def parse_money(series: pd.Series) -> pd.Series:
    """Parsing nilai uang untuk PostgreSQL NUMERIC(12,2)."""

    def convert(value):
        if pd.isna(value):
            return None

        text = str(value).strip()

        if not text:
            return None

        try:
            amount = Decimal(text)
        except InvalidOperation:
            return None

        # Tolak NaN dan Infinity.
        if not amount.is_finite():
            return None

        # NUMERIC(12,2): maksimal 10 digit sebelum desimal.
        if abs(amount) >= Decimal("10000000000"):
            return None

        # Tolak nilai dengan lebih dari 2 digit desimal
        # jika memerlukan pembulatan.
        if amount != amount.quantize(Decimal("0.01")):
            return None

        return amount.quantize(Decimal("0.01"))

    return series.map(convert)

def parse_column(
    series: pd.Series,
    column: ColumnSpec,
) -> pd.Series:
    """Parsing kolom berdasarkan tipe pada kontrak."""

    pg_type = column.pg_type.upper()

    # ZIP prefix harus tetap berupa teks lima digit.
    if column.name.endswith("_zip_code_prefix"):
        return parse_zip_prefix(series)

    if pg_type == "INTEGER":
        return parse_integer(series)

    if pg_type == "TIMESTAMP":
        return parse_timestamp(series)

    if pg_type == "NUMERIC(12,2)":
        return parse_money(series)

    if pg_type == "DOUBLE PRECISION":
        return pd.to_numeric(series, errors="coerce")

    if pg_type.startswith("VARCHAR") or pg_type == "TEXT":
        return series.astype("string")

    raise ValueError(
        f"Tipe kolom belum didukung: "
        f"{column.name} ({column.pg_type})"
    )

def parse_table(
    df: pd.DataFrame,
    table_name: str,
) -> pd.DataFrame:
    """Parsing seluruh kolom tabel berdasarkan kontrak."""

    if table_name not in TABLE_SCHEMAS:
        raise ValueError(f"Tabel tidak dikenal: {table_name}")

    table_spec = TABLE_SCHEMAS[table_name]

    expected_columns = [
        column.name for column in table_spec.columns
    ]

    actual_columns = df.columns.tolist()

    missing = sorted(set(expected_columns) - set(actual_columns))
    unexpected = sorted(set(actual_columns) - set(expected_columns))

    if missing or unexpected or actual_columns != expected_columns:
        raise ValueError(
            f"Schema drift pada {table_name}: "
            f"missing={missing}, "
            f"unexpected={unexpected}"
        )

    parsed = pd.DataFrame(index=df.index)

    for column in table_spec.columns:
        parsed[column.name] = parse_column(
            df[column.name],
            column,
        )

    return parsed

def detect_parse_failures(
    source: pd.DataFrame,
    parsed: pd.DataFrame,
    table_name: str,
) -> pd.DataFrame:
    """Mendeteksi nilai nonkosong yang gagal dikonversi."""

    table_spec = TABLE_SCHEMAS[table_name]
    failures = []

    for column in table_spec.columns:
        name = column.name

        original = source[name].astype("string").str.strip()
        original_present = original.notna() & original.ne("").fillna(False)

        parsed_missing = parsed[name].isna()

        failed = original_present & parsed_missing

        for row_index in source.index[failed]:
            failures.append({
                "source_row": row_index,
                "column": name,
                "original_value": str(source.at[row_index, name]),
                "reason": f"parse_failed:{column.pg_type}",
            })

    return pd.DataFrame(
        failures,
        columns=[
            "source_row",
            "column",
            "original_value",
            "reason",
        ],
    )

def quarantine_parse_failures(
    source: pd.DataFrame,
    parsed: pd.DataFrame,
    failures: pd.DataFrame,
    table_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pisahkan record valid dan karantina berdasarkan kegagalan parsing."""

    if not source.index.equals(parsed.index):
        raise ValueError("Index source dan parsed tidak sesuai")

    if failures.empty:
        return parsed.copy(), pd.DataFrame(
            columns=[
                *source.columns,
                "source_table",
                "source_row",
                "reason",
            ]
        )

    # Satu baris sumber hanya masuk karantina satu kali.
    failed_rows = failures["source_row"].drop_duplicates().tolist()

    quarantine = source.loc[failed_rows].copy()

    # Catat tabel dan nomor baris sumber.
    quarantine["source_table"] = table_name
    quarantine["source_row"] = quarantine.index

    # Gabungkan semua alasan pelanggaran per baris.
    reasons = (
        failures.groupby("source_row", sort=False)
        .apply(
            lambda group: "; ".join(
                f"{row.column}={row.original_value!r}: {row.reason}"
                for row in group.itertuples(index=False)
            ),
            include_groups=False,
        )
    )

    quarantine["reason"] = quarantine.index.map(reasons)

    # Baris valid masuk Silver.
    silver = parsed.drop(index=failed_rows).copy()

    return silver, quarantine

def detect_null_violations(
    source: pd.DataFrame,
    parsed: pd.DataFrame,
    table_name: str,
) -> pd.DataFrame:
    """Mendeteksi kolom wajib yang bernilai kosong."""

    table_spec = TABLE_SCHEMAS[table_name]
    violations = []

    for column in table_spec.columns:
        if column.nullable:
            continue

        name = column.name

        original = source[name].astype("string").str.strip()

        # Nilai kosong di sumber, bukan kegagalan parsing.
        missing = original.isna() | original.eq("").fillna(False)

        for row_index in source.index[missing]:
            violations.append({
                "source_row": row_index,
                "column": name,
                "original_value": None,
                "reason": "required_value_missing",
            })

    return pd.DataFrame(
        violations,
        columns=[
            "source_row",
            "column",
            "original_value",
            "reason",
        ],
    )

def collect_basic_violations(
    source: pd.DataFrame,
    parsed: pd.DataFrame,
    table_name: str,
) -> pd.DataFrame:
    """Menggabungkan pelanggaran parsing dan NOT NULL."""

    parse_failures = detect_parse_failures(
        source,
        parsed,
        table_name,
    )

    null_violations = detect_null_violations(
        source,
        parsed,
        table_name,
    )

    return pd.concat(
        [parse_failures, null_violations],
        ignore_index=True,
    )