
"""F05: Full batch rerun idempotency test.

Run:
    python -B -m scripts.failure_f05_batch_rerun

Pipeline:
    Bronze -> Silver -> Raw -> DW -> Gold Marts

No Docker volume reset and no Kafka producer replay.
Evidence: outputs/f05_batch_rerun.json
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pyarrow.parquet as pq
import pandas as pd
from dotenv import load_dotenv
from psycopg import sql

from olist.bronze import (
    BUCKET_NAME,
    RAW_DIR,
    calculate_sha256,
    create_minio_client,
    read_manifest,
)

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_PATH = ROOT / "outputs" / "f05_batch_rerun.json"
SILVER_DIR = ROOT / "outputs" / "silver"

SCHEMAS = ("raw", "dw", "mart")

# Kolom metadata proses yang boleh berubah saat rebuild.
# Kolom bisnis dan timestamp kejadian tetap dibandingkan.
VOLATILE_COLUMNS = {
    "updated_at",
    "created_at",
    "loaded_at",
    "generated_at",
    "etl_loaded_at",
    "processed_at",
    "refreshed_at",
}

COMMANDS = (
    ("Bronze", ("bronze",)),
    ("Silver", ("silver",)),
    ("Raw", ("load",)),
    ("DW", ("model",)),
    ("Gold Marts", ("marts",)),
)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def database_connection():
    load_dotenv(ROOT / ".env")

    return psycopg.connect(
        host="localhost",
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def source_snapshot():
    files = sorted(RAW_DIR.glob("*.csv"))

    if len(files) != 9:
        raise AssertionError(
            f"Expected 9 source CSVs, found {len(files)}"
        )

    return {
        path.name: calculate_sha256(path)
        for path in files
    }


def bronze_snapshot():
    client = create_minio_client()

    files = sorted(RAW_DIR.glob("*.csv"))
    result = {}

    for path in files:
        manifest = read_manifest(client, path.stem)

        if manifest is None:
            raise AssertionError(
                f"Missing Bronze manifest: {path.stem}"
            )

        versions = manifest.get("versions", [])
        latest_key = manifest.get("latest_object_key")

        if not latest_key:
            raise AssertionError(
                f"Missing latest object: {path.stem}"
            )

        # Verify latest object still exists in MinIO.
        obj = client.head_object(
            Bucket=BUCKET_NAME,
            Key=latest_key,
        )

        result[path.stem] = {
            "latest_sha256": manifest.get("latest_sha256"),
            "latest_object_key": latest_key,
            "version_checksums": sorted(
                version["sha256"]
                for version in versions
            ),
            "object_size": obj["ContentLength"],
        }

    return result


def parquet_content_fingerprint(path):
    """Hash logical row values rather than Parquet file metadata."""

    parquet = pq.ParquetFile(path)
    digest = hashlib.sha256()

    digest.update(
        json.dumps(
            parquet.schema_arrow.names,
            ensure_ascii=False,
        ).encode("utf-8")
    )

    for batch in parquet.iter_batches(batch_size=50_000):
        frame = batch.to_pandas()

        row_hashes = pd.util.hash_pandas_object(
            frame,
            index=False,
        )

        digest.update(
            row_hashes.to_numpy(dtype="uint64").tobytes()
        )

    return {
        "rows": parquet.metadata.num_rows,
        "content_sha256": digest.hexdigest(),
    }


def silver_snapshot():
    """Fingerprint sembilan dataset Silver berdasarkan kontrak schema."""

    from olist.schema import TABLE_SCHEMAS

    expected_tables = set(TABLE_SCHEMAS)

    paths = {
        path.stem: path
        for path in SILVER_DIR.glob("*.parquet")
    }

    missing = expected_tables - set(paths)
    extra = set(paths) - expected_tables

    if missing:
        raise AssertionError(
            f"Missing Silver Parquets: {sorted(missing)}"
        )

    if extra:
        print(
            "Additional Parquets excluded from main Silver snapshot:",
            sorted(extra),
            flush=True,
        )

    result = {
        table_name: parquet_content_fingerprint(
            paths[table_name]
        )
        for table_name in sorted(expected_tables)
    }

    assert len(result) == 9

    return result


def table_names(conn, schema_name):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """,
            (schema_name,),
        )

        return [row[0] for row in cur.fetchall()]


def table_columns(conn, schema_name, table_name):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema_name, table_name),
        )

        return [row[0] for row in cur.fetchall()]


def table_fingerprint(conn, schema_name, table_name):
    columns = table_columns(conn, schema_name, table_name)

    stable_columns = [
        col
        for col in columns
        if col.lower() not in VOLATILE_COLUMNS
    ]

    if not stable_columns:
        raise AssertionError(
            f"No stable columns: {schema_name}.{table_name}"
        )

    # Row hashing is independent of table physical row order.
    # SUM creates a compact, order-independent fingerprint.
    # This is a strong practical regression check,
    # but not a cryptographic proof of equality.
    row_data = sql.SQL("json_build_array({})").format(
        sql.SQL(", ").join(
            sql.Identifier(col)
            for col in stable_columns
        )
    )

    statement = sql.SQL("""
        SELECT
            COUNT(*),
            COALESCE(
                SUM(
                    hashtextextended(
                        {}::text,
                        0
                    )
                ),
                0
            )::text
        FROM {}.{}
    """).format(
        row_data,
        sql.Identifier(schema_name),
        sql.Identifier(table_name),
    )

    with conn.cursor() as cur:
        cur.execute(statement)
        count, fingerprint = cur.fetchone()

    return {
        "rows": count,
        "fingerprint": fingerprint,
        "excluded_columns": [
            col
            for col in columns
            if col not in stable_columns
        ],
    }


def postgres_snapshot():
    result = {}

    with database_connection() as conn:
        for schema_name in SCHEMAS:
            names = table_names(conn, schema_name)

            if not names:
                raise AssertionError(
                    f"No base tables in schema {schema_name}"
                )

            schema_result = {}

            for table_name in names:
                print(
                    f"  Hashing {schema_name}.{table_name}",
                    flush=True,
                )

                schema_result[table_name] = table_fingerprint(
                    conn,
                    schema_name,
                    table_name,
                )

            result[schema_name] = schema_result

    return result


def snapshot(label):
    print(f"\n=== {label} SNAPSHOT ===", flush=True)

    return {
        "source": source_snapshot(),
        "bronze": bronze_snapshot(),
        "silver": silver_snapshot(),
        "postgres": postgres_snapshot(),
    }


def run_pipeline_step(label, arguments):
    command = [
        sys.executable,
        "-B",
        str(ROOT / "pipeline.py"),
        *arguments,
    ]

    print(
        f"\n>>> [{label}] {' '.join(command)}",
        flush=True,
    )

    started = time.perf_counter()

    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        timeout=900,
    )

    duration = round(time.perf_counter() - started, 2)

    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed: exit={result.returncode}"
        )

    print(
        f"PASS: {label} ({duration:.2f}s)",
        flush=True,
    )

    return {
        "step": label,
        "seconds": duration,
        "exit_code": result.returncode,
    }


def compare_snapshots(before, after):
    results = {}

    for key in ("source", "bronze", "silver", "postgres"):
        results[key] = before[key] == after[key]

    return results


def summary_rows(snapshot_data):
    return {
        schema_name: {
            table_name: details["rows"]
            for table_name, details in tables.items()
        }
        for schema_name, tables in
        snapshot_data["postgres"].items()
    }


def main():
    print("=== F05 FULL BATCH RERUN TEST ===", flush=True)

    EVIDENCE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    evidence = {
        "scenario": "F05_FULL_BATCH_RERUN",
        "started_at_utc": utc_now(),
        "steps": [],
        "verdict": "INCOMPLETE",
    }

    try:
        before = snapshot("BEFORE")

        for label, arguments in COMMANDS:
            step = run_pipeline_step(label, arguments)
            evidence["steps"].append(step)

        after = snapshot("AFTER")

        checks = compare_snapshots(before, after)

        # Independent reconciliation checks after rebuild.
        print(
            "\n=== POST-RERUN RECONCILIATION ===",
            flush=True,
        )

        for module in (
            "scripts.verify_raw_counts",
            "scripts.verify_stream_status",
        ):
            print(f">>> {module}", flush=True)

            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    module,
                ],
                cwd=ROOT,
                check=True,
                timeout=180,
            )

        # Integrity tests are run inside pipeline model/marts,
        # but an additional combined run is useful here.
        print("\n>>> Combined integrity tests", flush=True)

        subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "-q",
                "tests/test_dw_integrity.py",
                "tests/test_marts.py",
            ],
            cwd=ROOT,
            check=True,
            timeout=180,
        )

        verdict = (
            "TERTANGKAP"
            if all(checks.values())
            else "FAIL"
        )

        evidence.update({
            "checks": checks,
            "source_csv_count": len(after["source"]),
            "bronze_dataset_count": len(after["bronze"]),
            "silver_parquet_count": len(after["silver"]),
            "silver_total_rows": sum(
                entry["rows"]
                for entry in after["silver"].values()
            ),
            "postgres_rows_before": summary_rows(before),
            "postgres_rows_after": summary_rows(after),
            "differences": {
                key: {
                    "before": before[key],
                    "after": after[key],
                }
                for key in checks
                if not checks[key]
            },
            "verdict": verdict,
        })

        print("\n=== F05 RESULTS ===")
        print(f"Source unchanged: {checks['source']}")
        print(f"Bronze unchanged: {checks['bronze']}")
        print(f"Silver unchanged: {checks['silver']}")
        print(f"PostgreSQL unchanged: {checks['postgres']}")
        print(
            f"Silver rows: "
            f"{evidence['silver_total_rows']:,}"
        )
        print(f"F05 verdict: {verdict}")

        if verdict != "TERTANGKAP":
            raise AssertionError(
                "F05 snapshots differ; inspect evidence JSON"
            )

    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"

        if evidence["verdict"] == "INCOMPLETE":
            evidence["verdict"] = "FAIL"

        raise

    finally:
        evidence["finished_at_utc"] = utc_now()

        EVIDENCE_PATH.write_text(
            json.dumps(
                evidence,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        print(
            f"\nEvidence saved: {EVIDENCE_PATH}",
            flush=True,
        )


if __name__ == "__main__":
    main()
