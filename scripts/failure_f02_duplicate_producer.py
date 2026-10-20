
"""F02: Verify idempotency after running the Kafka producer twice.

Run:
    python -B -m scripts.failure_f02_duplicate_producer

Uses existing Kafka topics and PostgreSQL stream tables.
Does not delete or reset existing data.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
METRICS_FILE = ROOT / "outputs" / "consumer_metrics.json"

ORDER_LIMIT = 20
SEED = 42


def connect():
    load_dotenv(ROOT / ".env")

    return psycopg.connect(
        host="localhost",
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def snapshot():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*)
                FROM stream.order_events
            """)
            event_count = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*)
                FROM stream.order_current
            """)
            current_count = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*)
                FROM stream.order_dlq
            """)
            dlq_count = cur.fetchone()[0]

            cur.execute("""
                SELECT order_id, status_rank
                FROM stream.order_current
            """)
            ranks = dict(cur.fetchall())

    return {
        "events": event_count,
        "current": current_count,
        "dlq": dlq_count,
        "ranks": ranks,
    }


def run_module(module, *args):
    command = [
        sys.executable,
        "-B",
        "-m",
        module,
        *args,
    ]

    print("\n>>> " + " ".join(command), flush=True)

    subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        timeout=180,
    )


def check_duplicate_event_ids():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*)
                FROM (
                    SELECT event_id
                    FROM stream.order_events
                    GROUP BY event_id
                    HAVING COUNT(*) > 1
                ) duplicates
            """)

            return cur.fetchone()[0]


def main():
    print("=== F02 DUPLICATE PRODUCER TEST ===")

    before = snapshot()

    print(f"Events before: {before['events']:,}")
    print(f"Orders before: {before['current']:,}")
    print(f"DLQ before: {before['dlq']:,}")

    # Both runs use identical order limits and random seeds.
    # Event IDs remain deterministic across runs.
    for run_number in (1, 2):
        print(
            f"\nProducer run {run_number}/2",
            flush=True,
        )

        run_module(
            "scripts.produce_orders",
            "--limit",
            str(ORDER_LIMIT),
            "--seed",
            str(SEED),
        )

    # Consume both runs using the existing consumer group.
    # Do not reset the committed Kafka offsets.
    print("\nConsuming replayed events...", flush=True)

    if METRICS_FILE.exists():
        METRICS_FILE.unlink()

    run_module(
        "scripts.consume_orders",
        "--idle-seconds",
        "8",
        "--batch-size",
        "200",
    )

    if not METRICS_FILE.exists():
        raise AssertionError(
            "Consumer metrics file was not created"
        )

    metrics = json.loads(
        METRICS_FILE.read_text(encoding="utf-8")
    )

    after = snapshot()
    duplicate_ids = check_duplicate_event_ids()

    regressions = []

    for order_id, previous_rank in before["ranks"].items():
        new_rank = after["ranks"].get(order_id)

        if new_rank is None or new_rank < previous_rank:
            regressions.append(order_id)

    print("\n=== F02 RESULTS ===")
    print(f"Events before: {before['events']:,}")
    print(f"Events after: {after['events']:,}")
    print(f"Orders before: {before['current']:,}")
    print(f"Orders after: {after['current']:,}")
    print(f"DLQ before: {before['dlq']:,}")
    print(f"DLQ after: {after['dlq']:,}")
    print(f"Duplicate event IDs: {duplicate_ids}")
    print(f"Status regressions: {len(regressions)}")
    print(
        "Consumer duplicate classifications: "
        f"{metrics.get('duplicate', 0):,}"
    )
    print(
        "Consumer messages processed: "
        f"{metrics.get('messages', 0):,}"
    )

    assert metrics.get("messages", 0) > 0, (
        "Consumer did not process Kafka messages"
    )

    assert metrics.get("duplicate", 0) > 0, (
        "No duplicate events were detected by consumer"
    )

    assert duplicate_ids == 0, (
        "Duplicate event IDs persisted in PostgreSQL"
    )

    assert not regressions, (
        f"Order status regression detected: "
        f"{regressions[:5]}"
    )

    assert after["events"] >= before["events"], (
        "Persisted event count unexpectedly decreased"
    )

    assert after["current"] >= before["current"], (
        "Current order count unexpectedly decreased"
    )

    print("\nF02 verdict: TERTANGKAP")
    print("PostgreSQL event idempotency: PASS")
    print("Order status monotonicity: PASS")


if __name__ == "__main__":
    main()
