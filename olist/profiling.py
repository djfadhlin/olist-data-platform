"""T0 Olist profiling: deterministic statistics, Markdown and JSON evidence."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = ROOT / "outputs"

KEY_COLUMNS = {
    "olist_orders_dataset": ["order_id"],
    "olist_order_items_dataset": ["order_id", "order_item_id"],
    "olist_order_payments_dataset": ["order_id", "payment_sequential"],
    "olist_order_reviews_dataset": ["review_id", "order_id"],
    "olist_customers_dataset": ["customer_id"],
    "olist_sellers_dataset": ["seller_id"],
    "olist_products_dataset": ["product_id"],
    "olist_geolocation_dataset": ["geolocation_zip_code_prefix"],
    "product_category_name_translation": ["product_category_name"],
}

TIMESTAMP_COLUMNS = {
    "olist_orders_dataset": [
        "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "olist_order_items_dataset": ["shipping_limit_date"],
    "olist_order_reviews_dataset": ["review_creation_date", "review_answer_timestamp"],
}


def read_tables(raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    files = sorted(raw_dir.glob("*.csv"))
    expected = {f"{name}.csv" for name in KEY_COLUMNS}
    found = {p.name for p in files}
    if found != expected:
        raise ValueError(f"CSV berbeda dari kontrak. Missing={sorted(expected-found)}; extra={sorted(found-expected)}")
    return {
        p.stem: pd.read_csv(p, dtype=str, encoding="utf-8-sig", low_memory=False)
        for p in files
    }


def profile_table(name: str, df: pd.DataFrame) -> dict:
    keys = KEY_COLUMNS[name]
    missing = [k for k in keys if k not in df.columns]
    if missing:
        raise ValueError(f"{name}: key columns missing: {missing}")
    null_counts = df.isna().sum()
    null_key_rows = int(df[keys].isna().any(axis=1).sum())
    dup_keys = int(df.duplicated(subset=keys).sum())
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "duplicate_rows": int(df.duplicated().sum()),
        "null_counts": {c: int(v) for c, v in null_counts.items()},
        "null_percentages": {c: round(int(v)*100/len(df), 2) if len(df) else 0.0 for c,v in null_counts.items()},
        "candidate_key": keys,
        "duplicate_keys": dup_keys,
        "null_key_rows": null_key_rows,
        "key_unique": dup_keys == 0 and null_key_rows == 0,
    }


def analyze_reviews(df: pd.DataFrame) -> dict:
    per_order = df.groupby("order_id").size()
    return {
        "review_id_duplicate_rows": int(df.duplicated(["review_id"]).sum()),
        "order_id_duplicate_rows": int(df.duplicated(["order_id"]).sum()),
        "review_order_composite_duplicate_rows": int(df.duplicated(["review_id", "order_id"]).sum()),
        "orders_with_multiple_reviews": int((per_order > 1).sum()),
        "orders_with_review": int(per_order.size),
        "max_reviews_per_order": int(per_order.max()),
    }


def parse_time(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, format="%Y-%m-%d %H:%M:%S", errors="coerce")


def analyze_timestamps(tables: dict[str, pd.DataFrame]) -> dict:
    out = {}
    for name, columns in TIMESTAMP_COLUMNS.items():
        out[name] = {}
        for col in columns:
            original = tables[name][col]
            parsed = parse_time(original)
            out[name][col] = {
                "min": str(parsed.min()) if parsed.notna().any() else None,
                "max": str(parsed.max()) if parsed.notna().any() else None,
                "null_source": int(original.isna().sum()),
                "invalid_non_null": int((original.notna() & parsed.isna()).sum()),
            }
    return out


def analyze_relationships(tables: dict[str, pd.DataFrame]) -> dict:
    orders = tables["olist_orders_dataset"]
    items = tables["olist_order_items_dataset"]
    payments = tables["olist_order_payments_dataset"]
    customers = tables["olist_customers_dataset"]
    frequency = customers.groupby("customer_unique_id")["customer_id"].nunique()
    return {
        "total_orders": len(orders),
        "orders_without_items": int((~orders.order_id.isin(items.order_id)).sum()),
        "orders_without_payments": int((~orders.order_id.isin(payments.order_id)).sum()),
        "unique_customer_ids": int(customers.customer_id.nunique()),
        "unique_people": int(customers.customer_unique_id.nunique()),
        "people_with_multiple_customer_ids": int((frequency > 1).sum()),
    }


def analyze_order_anomalies(df: pd.DataFrame) -> dict:
    purchase = parse_time(df["order_purchase_timestamp"])
    approved = parse_time(df["order_approved_at"])
    carrier = parse_time(df["order_delivered_carrier_date"])
    delivered = parse_time(df["order_delivered_customer_date"])
    return {
        "delivered_without_delivery_date": int(((df.order_status == "delivered") & delivered.isna()).sum()),
        "delivery_before_carrier": int((delivered < carrier).sum()),
        "approval_before_purchase": int((approved < purchase).sum()),
    }


def analyze_geolocation(df: pd.DataFrame) -> dict:
    lat = pd.to_numeric(df.geolocation_lat, errors="coerce")
    lng = pd.to_numeric(df.geolocation_lng, errors="coerce")
    numeric = lat.notna() & lng.notna()
    outside = numeric & (~lat.between(-34, 5) | ~lng.between(-74, -35))
    return {
        "total_rows": len(df),
        "unique_zip_prefixes": int(df.geolocation_zip_code_prefix.nunique()),
        "invalid_numeric_coordinates": int((~numeric).sum()),
        "outside_brazil_approx_bounds": int(outside.sum()),
        "latitude_min": float(lat.min()),
        "latitude_max": float(lat.max()),
        "longitude_min": float(lng.min()),
        "longitude_max": float(lng.max()),
    }


def analyze_reconciliation(tables: dict[str, pd.DataFrame]) -> dict:
    orders = tables["olist_orders_dataset"]["order_id"]
    items = tables["olist_order_items_dataset"]
    payments = tables["olist_order_payments_dataset"]
    # Preserve decimal cents exactly; do not merge item and payment rows before aggregation.
    item_total = pd.Series(
        [Decimal(p) + Decimal(f) for p, f in zip(items.price, items.freight_value)],
        index=items.index,
    ).groupby(items.order_id).sum()
    payment_total = payments.payment_value.map(Decimal).groupby(payments.order_id).sum()
    a = orders.map(item_total)
    b = orders.map(payment_total)
    no_items = a.isna()
    no_payments = b.isna()
    a = a.map(lambda x: Decimal("0") if pd.isna(x) else x)
    b = b.map(lambda x: Decimal("0") if pd.isna(x) else x)
    difference = [abs(x-y) for x,y in zip(a,b)]
    return {
        "total_orders": len(orders),
        "orders_without_items": int(no_items.sum()),
        "orders_without_payments": int(no_payments.sum()),
        "difference_gt_0_01": sum(x > Decimal("0.01") for x in difference),
        "difference_gt_1_00": sum(x > Decimal("1.00") for x in difference),
        "within_0_01": sum(x <= Decimal("0.01") for x in difference),
        "treatment": "missing totals compared as zero; missing flags counted separately",
    }


def build_report(data: dict) -> str:
    lines = ["# Olist Data Profiling Report", "", "Generated from source CSV by `python -m olist.profiling`.", "", "## Ringkasan dan natural key", "", "| Tabel | Baris | Kolom | Exact duplicates | Kandidat key | Duplicate key rows | Null key rows | Unik |", "|---|---:|---:|---:|---|---:|---:|---|"]
    for name, stat in data["tables"].items():
        lines.append(f"| {name} | {stat['rows']:,} | {stat['columns']} | {stat['duplicate_rows']:,} | {', '.join(stat['candidate_key'])} | {stat['duplicate_keys']:,} | {stat['null_key_rows']:,} | {'Ya' if stat['key_unique'] else 'Tidak'} |")
    lines += ["", "Catatan: key pada tabel reviews adalah kombinasi `(review_id, order_id)`; ZIP prefix bukan key unik di sumber geolocation.", "", "## Missing values", ""]
    for name, stat in data["tables"].items():
        lines += [f"### {name}", "", "| Kolom | Null count | Null % |", "|---|---:|---:|"]
        for col, count in stat["null_counts"].items():
            lines.append(f"| {col} | {count:,} | {stat['null_percentages'][col]:.2f}% |")
        lines.append("")
    lines += ["## Timestamp ranges and validity", "", "| Tabel | Kolom | Min | Max | Null sumber | Invalid non-null |", "|---|---|---|---|---:|---:|"]
    for name, cols in data["timestamps"].items():
        for col, v in cols.items():
            lines.append(f"| {name} | {col} | {v['min']} | {v['max']} | {v['null_source']:,} | {v['invalid_non_null']:,} |")
    for section, title in [("reviews", "Review key analysis"), ("relationships", "Cross-table relationships"), ("order_anomalies", "Order anomalies"), ("geolocation", "Geolocation anomalies"), ("reconciliation", "Payment reconciliation")]:
        lines += ["", f"## {title}", "", "| Metrik | Hasil |", "|---|---:|"]
        for k, v in data[section].items():
            lines.append(f"| {k} | {v:,} |" if isinstance(v, int) else f"| {k} | {v} |")
    lines += ["", "## Catatan interpretasi", "", "- Bounding box Brasil adalah pendekatan kasar, bukan batas negara yang presisi.", "- Missing tanggal pada status non-delivered belum tentu merupakan error.", "- Rekonsiliasi belum mengklasifikasikan penyebab selisih; itu dikerjakan pada mart.", "- Nilai sumber tidak diubah atau dibuang oleh proses profiling.", ""]
    return "\n".join(lines)


def run_profile(raw_dir: Path = RAW_DIR, output_dir: Path = OUTPUT_DIR) -> dict:
    tables = read_tables(raw_dir)
    data = {
        "tables": {name: profile_table(name, df) for name,df in tables.items()},
        "reviews": analyze_reviews(tables["olist_order_reviews_dataset"]),
        "timestamps": analyze_timestamps(tables),
        "relationships": analyze_relationships(tables),
        "order_anomalies": analyze_order_anomalies(tables["olist_orders_dataset"]),
        "geolocation": analyze_geolocation(tables["olist_geolocation_dataset"]),
        "reconciliation": analyze_reconciliation(tables),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "profile.md").write_text(build_report(data), encoding="utf-8")
    (output_dir / "profile.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"9 CSV diprofilkan. Laporan: {output_dir / 'profile.md'}")
    print(f"Data terstruktur: {output_dir / 'profile.json'}")
    print("Reviews multi-order:", data["reviews"]["orders_with_multiple_reviews"])
    print("Koordinat di luar batas:", data["geolocation"]["outside_brazil_approx_bounds"])
    print("Mismatch > BRL 0.01:", data["reconciliation"]["difference_gt_0_01"])
    return data


if __name__ == "__main__":
    run_profile()
