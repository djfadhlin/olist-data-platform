"""Aturan kualitas data berdasarkan DATA_CONTRACT.md."""

import pandas as pd

from olist.silver import parse_integer, parse_money, parse_timestamp

def check_h01_orders_id(source: pd.DataFrame) -> pd.DataFrame:
    """H01: order_id pada Orders wajib terisi."""

    values = source["order_id"].astype("string").str.strip()

    invalid = values.isna() | values.eq("").fillna(False)

    violations = []

    for row_index in source.index[invalid]:
        violations.append({
            "source_row": row_index,
            "column": "order_id",
            "original_value": source.at[row_index, "order_id"],
            "reason": "H01: order_id wajib terisi",
            "rule_id": "H01",
        })

    return pd.DataFrame(
        violations,
        columns=[
            "source_row",
            "column",
            "original_value",
            "reason",
            "rule_id",
        ],
    )

def check_h02_orders_unique(source: pd.DataFrame) -> pd.DataFrame:
    """H02: order_id harus unik; pertahankan kemunculan pertama."""

    values = source["order_id"].astype("string").str.strip()

    # Nilai kosong ditangani oleh H01.
    valid_key = values.notna() & values.ne("").fillna(False)

    duplicated = values.duplicated(keep="first") & valid_key

    violations = []

    for row_index in source.index[duplicated]:
        violations.append({
            "source_row": row_index,
            "column": "order_id",
            "original_value": source.at[row_index, "order_id"],
            "reason": "H02: duplicate order_id",
            "rule_id": "H02",
        })

    return pd.DataFrame(
        violations,
        columns=[
            "source_row",
            "column",
            "original_value",
            "reason",
            "rule_id",
        ],
    )

def check_h03_purchase_timestamp(source: pd.DataFrame) -> pd.DataFrame:
    """H03: order_purchase_timestamp harus valid dan tidak kosong."""

    column = "order_purchase_timestamp"

    parsed = parse_timestamp(source[column])
    invalid = parsed.isna()

    violations = []

    for row_index in source.index[invalid]:
        violations.append({
            "source_row": row_index,
            "column": column,
            "original_value": source.at[row_index, column],
            "reason": "H03: invalid order_purchase_timestamp",
            "rule_id": "H03",
        })

    return pd.DataFrame(
        violations,
        columns=[
            "source_row",
            "column",
            "original_value",
            "reason",
            "rule_id",
        ],
    )

def check_h04_order_items_key(source: pd.DataFrame) -> pd.DataFrame:
    """H04: key (order_id, order_item_id) wajib lengkap dan unik."""

    order_id = source["order_id"].astype("string").str.strip()
    item_id = pd.to_numeric(source["order_item_id"], errors="coerce")

    valid_order = order_id.notna() & order_id.ne("").fillna(False)
    valid_item = item_id.notna() & (item_id % 1 == 0)

    valid_key = valid_order & valid_item

    duplicate = pd.Series(False, index=source.index)
    duplicate.loc[valid_key] = pd.DataFrame({
        "order_id": order_id.loc[valid_key],
        "order_item_id": item_id.loc[valid_key],
    }).duplicated(keep="first").to_numpy()

    violations = []

    for row_index in source.index[~valid_key | duplicate]:
        reason = (
            "H04: incomplete_or_invalid_key"
            if not valid_key.loc[row_index]
            else "H04: duplicate_key"
        )

        violations.append({
            "source_row": row_index,
            "column": "order_id,order_item_id",
            "original_value": (
                f"{source.at[row_index, 'order_id']},"
                f"{source.at[row_index, 'order_item_id']}"
            ),
            "reason": reason,
            "rule_id": "H04",
        })

    return pd.DataFrame(
        violations,
        columns=[
            "source_row",
            "column",
            "original_value",
            "reason",
            "rule_id",
        ],
    )


def check_h05_item_amounts(source: pd.DataFrame) -> pd.DataFrame:
    """H05: price dan freight_value harus valid, non-NULL, dan >= 0."""

    violations = []

    for column in ("price", "freight_value"):
        parsed = parse_money(source[column])

        invalid = parsed.map(
            lambda value: pd.isna(value) or value < 0
        ).fillna(True)

        for row_index in source.index[invalid]:
            violations.append({
                "source_row": row_index,
                "column": column,
                "original_value": source.at[row_index, column],
                "reason": f"H05: invalid_or_negative_{column}",
                "rule_id": "H05",
            })

    return pd.DataFrame(
        violations,
        columns=[
            "source_row",
            "column",
            "original_value",
            "reason",
            "rule_id",
        ],
    )

def check_h06_payments_key(source: pd.DataFrame) -> pd.DataFrame:
    """H06: (order_id, payment_sequential) wajib lengkap dan unik."""

    from olist.silver import parse_integer

    order_id = source["order_id"].astype("string").str.strip()
    sequential = parse_integer(source["payment_sequential"])

    valid_order = order_id.notna() & order_id.ne("").fillna(False)
    valid_key = valid_order & sequential.notna()

    duplicate = pd.Series(False, index=source.index)

    duplicate.loc[valid_key] = pd.DataFrame({
        "order_id": order_id.loc[valid_key],
        "payment_sequential": sequential.loc[valid_key],
    }).duplicated(keep="first").to_numpy()

    violations = []

    for row_index in source.index[~valid_key | duplicate]:
        reason = (
            "H06: incomplete_or_invalid_key"
            if not valid_key.loc[row_index]
            else "H06: duplicate_key"
        )

        violations.append({
            "source_row": row_index,
            "column": "order_id,payment_sequential",
            "original_value": (
                f"{source.at[row_index, 'order_id']},"
                f"{source.at[row_index, 'payment_sequential']}"
            ),
            "reason": reason,
            "rule_id": "H06",
        })

    return pd.DataFrame(
        violations,
        columns=[
            "source_row",
            "column",
            "original_value",
            "reason",
            "rule_id",
        ],
    )

def _make_violations(source, invalid, column, reason, rule_id):
    """Bangun daftar pelanggaran dengan format yang konsisten."""
    rows = [
        {
            "source_row": idx,
            "column": column,
            "original_value": source.at[idx, column]
            if column in source.columns else None,
            "reason": reason,
            "rule_id": rule_id,
        }
        for idx in source.index[invalid]
    ]
    return pd.DataFrame(
        rows,
        columns=["source_row", "column", "original_value",
                 "reason", "rule_id"],
    )


def _check_unique_key(source, columns, rule_id):
    """Validasi natural key lengkap dan unik; simpan baris pertama."""
    keys = pd.DataFrame(index=source.index)

    for column in columns:
        if column == "review_score":
            keys[column] = parse_integer(source[column])
        else:
            keys[column] = source[column].astype("string").str.strip()

    valid = keys.notna().all(axis=1)

    for column in columns:
        if column != "review_score":
            valid &= keys[column].ne("").fillna(False)

    duplicate = pd.Series(False, index=source.index)
    duplicate.loc[valid] = keys.loc[valid].duplicated(
        keep="first"
    ).to_numpy()

    invalid = ~valid | duplicate

    rows = []
    for idx in source.index[invalid]:
        reason = (
            f"{rule_id}: duplicate_key"
            if duplicate.loc[idx]
            else f"{rule_id}: incomplete_key"
        )
        rows.append({
            "source_row": idx,
            "column": ",".join(columns),
            "original_value": "|".join(
                str(source.at[idx, col]) for col in columns
            ),
            "reason": reason,
            "rule_id": rule_id,
        })

    return pd.DataFrame(
        rows,
        columns=["source_row", "column", "original_value",
                 "reason", "rule_id"],
    )


def check_h07_payment_value(source: pd.DataFrame) -> pd.DataFrame:
    """H07: payment_value valid, non-NULL, dan >= 0."""
    values = parse_money(source["payment_value"])
    invalid = values.map(
        lambda value: pd.isna(value) or value < 0
    )
    return _make_violations(
        source, invalid, "payment_value",
        "H07: invalid_or_negative_payment_value", "H07"
    )


def check_h08_customers(source: pd.DataFrame) -> pd.DataFrame:
    """H08: customer_id dan customer_unique_id wajib terisi;
    customer_id harus unik."""
    customer_id = source["customer_id"].astype("string").str.strip()
    unique_id = source["customer_unique_id"].astype("string").str.strip()

    missing = (
        customer_id.isna() | customer_id.eq("").fillna(False)
        | unique_id.isna() | unique_id.eq("").fillna(False)
    )
    duplicate = customer_id.duplicated(keep="first") & (
        customer_id.notna() & customer_id.ne("").fillna(False)
    )
    return _make_violations(
        source, missing | duplicate, "customer_id",
        "H08: missing_or_duplicate_customer_key", "H08"
    )


def check_h09_products(source: pd.DataFrame) -> pd.DataFrame:
    """H09: product_id wajib terisi dan unik."""
    return _check_unique_key(source, ("product_id",), "H09")


def check_h10_reviews(source: pd.DataFrame) -> pd.DataFrame:
    """H10: (review_id, order_id) lengkap dan unik;
    review_score berupa integer 1 sampai 5."""
    key_violations = _check_unique_key(
        source, ("review_id", "order_id"), "H10"
    )

    score = parse_integer(source["review_score"])
    invalid_score = score.isna() | ~score.between(1, 5).fillna(False)

    score_violations = _make_violations(
        source, invalid_score, "review_score",
        "H10: review_score_out_of_range", "H10"
    )

    return pd.concat(
        [key_violations, score_violations],
        ignore_index=True,
    )

HARD_RULES = {
    "olist_orders_dataset": [
        check_h01_orders_id,
        check_h02_orders_unique,
        check_h03_purchase_timestamp,
    ],
    "olist_order_items_dataset": [
        check_h04_order_items_key,
        check_h05_item_amounts,
    ],
    "olist_order_payments_dataset": [
        check_h06_payments_key,
        check_h07_payment_value,
    ],
    "olist_customers_dataset": [
        check_h08_customers,
    ],
    "olist_products_dataset": [
        check_h09_products,
    ],
    "olist_order_reviews_dataset": [
        check_h10_reviews,
    ],
}


def run_hard_rules(source: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """Jalankan seluruh Hard Rules yang berlaku untuk sebuah tabel."""

    if table_name not in HARD_RULES:
        return pd.DataFrame(
            columns=[
                "source_row",
                "column",
                "original_value",
                "reason",
                "rule_id",
            ]
        )

    results = []

    for rule_function in HARD_RULES[table_name]:
        violations = rule_function(source)

    if not isinstance(violations, pd.DataFrame):
        raise TypeError(
            f"Hard rule {rule_function.__name__} pada "
            f"{table_name} mengembalikan "
            f"{type(violations).__name__}, "
            "seharusnya pandas DataFrame."
        )

    if not violations.empty:
        results.append(violations)

    if not results:
        return pd.DataFrame(
            columns=[
                "source_row",
                "column",
                "original_value",
                "reason",
                "rule_id",
            ]
        )

    return pd.concat(results, ignore_index=True)

from olist.silver import collect_basic_violations


def collect_all_hard_violations(
    source: pd.DataFrame,
    parsed: pd.DataFrame,
    table_name: str,
) -> pd.DataFrame:
    """Gabungkan validasi dasar dan hard rules.

    Duplikat pelanggaran teknis pada kolom yang sama dihapus
    jika sudah dijelaskan oleh aturan H01-H10.
    """

    basic = collect_basic_violations(source, parsed, table_name).copy()
    hard = run_hard_rules(source, table_name)

    if not basic.empty:
        basic["rule_id"] = "SCHEMA"

    # Prioritaskan rule kontrak ketika row dan kolom yang sama
    # juga terdeteksi oleh validasi dasar.
    if not basic.empty and not hard.empty:
        covered = set(
            zip(hard["source_row"], hard["column"])
        )

        basic = basic.loc[
            ~pd.Series(
                list(zip(basic["source_row"], basic["column"])),
                index=basic.index,
            ).isin(covered)
        ].copy()

    return pd.concat([hard, basic], ignore_index=True)