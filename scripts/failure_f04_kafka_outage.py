
"""F04: Kafka broker outage during producer replay.

Run:
    python -B -m scripts.failure_f04_kafka_outage

Stops only the Kafka container, never deletes Docker volumes.
Restarts Kafka in finally, even when the test fails.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from kafka import KafkaAdminClient


ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "outputs" / "f04_kafka_outage.json"

LIMIT = 100
SEED = 42
DELAY_MS = 50
OUTAGE_SECONDS = 6


def command(*args, check=True, timeout=180):
    return subprocess.run(
        list(args),
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=check,
        timeout=timeout,
    )


def show(result):
    if result.stdout:
        print(result.stdout, flush=True)
    if result.stderr:
        print(result.stderr, file=sys.stderr, flush=True)


def kafka_ready():
    try:
        admin = KafkaAdminClient(
            bootstrap_servers="localhost:29092",
            request_timeout_ms=3000,
            api_version_auto_timeout_ms=3000,
        )
        try:
            return "olist.order_events" in admin.list_topics()
        finally:
            admin.close()
    except Exception:
        return False


def wait_for_kafka(timeout=120):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if kafka_ready():
            return
        time.sleep(2)

    raise TimeoutError(
        "Kafka broker did not become ready after restart"
    )


def db_snapshot():
    load_dotenv(ROOT / ".env")

    with psycopg.connect(
        host="localhost",
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM stream.order_events")
            events = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM stream.order_current")
            current = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*)
                FROM (
                    SELECT event_id
                    FROM stream.order_events
                    GROUP BY event_id
                    HAVING COUNT(*) > 1
                ) x
            """)
            duplicate_ids = cur.fetchone()[0]

            cur.execute("""
                SELECT order_id, status_rank
                FROM stream.order_current
            """)
            ranks = dict(cur.fetchall())

    return {
        "events": events,
        "current": current,
        "duplicate_ids": duplicate_ids,
        "ranks": ranks,
    }


def run_python(module, *args, timeout=180):
    result = command(
        sys.executable,
        "-B",
        "-m",
        module,
        *args,
        check=False,
        timeout=timeout,
    )
    show(result)

    if result.returncode != 0:
        raise RuntimeError(
            f"{module} failed: exit={result.returncode}"
        )

    return result


def main():
    print("=== F04 KAFKA BROKER OUTAGE TEST ===", flush=True)
    print(
        "WARNING: Kafka will be unavailable temporarily.",
        flush=True,
    )

    if not kafka_ready():
        raise RuntimeError(
            "Kafka is not ready. Start Docker stack first."
        )

    before = db_snapshot()
    producer_command = [
        sys.executable,
        "-B",
        "-m",
        "scripts.produce_orders",
        "--limit",
        str(LIMIT),
        "--seed",
        str(SEED),
        "--delay-ms",
        str(DELAY_MS),
    ]

    producer = None
    outage_observed = False
    producer_exit_code = None
    producer_stdout = ""
    producer_stderr = ""
    started_at = datetime.now(timezone.utc).isoformat()

    try:
        print("\n[1] Starting throttled producer...", flush=True)

        producer = subprocess.Popen(
            producer_command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Allow producer time to begin sending.
        time.sleep(3)

        if producer.poll() is not None:
            stdout, stderr = producer.communicate()
            raise RuntimeError(
                "Producer finished before broker outage; "
                f"exit={producer.returncode}\n"
                f"{stdout}\n{stderr}"
            )

        print("\n[2] Stopping Kafka broker...", flush=True)

        stop_result = command(
            "docker", "compose", "stop", "kafka",
            check=False,
            timeout=90,
        )
        show(stop_result)

        if stop_result.returncode != 0:
            raise RuntimeError("Failed to stop Kafka")

        # Verify the outage really occurred.
        outage_observed = not kafka_ready()

        print(
            f"Kafka unavailable: {outage_observed}",
            flush=True,
        )

        if not outage_observed:
            raise AssertionError(
                "Kafka outage was not observed"
            )

        time.sleep(OUTAGE_SECONDS)

    finally:
        # Mandatory recovery, even if assertions fail.
        print("\n[3] Restoring Kafka broker...", flush=True)

        recovery = command(
            "docker", "compose", "start", "kafka",
            check=False,
            timeout=120,
        )
        show(recovery)

        if recovery.returncode != 0:
            raise RuntimeError(
                "Kafka restart failed. Inspect docker compose ps."
            )

        wait_for_kafka()

        print("Kafka broker recovered: True", flush=True)

        if producer is not None:
            try:
                producer_stdout, producer_stderr = (
                    producer.communicate(timeout=120)
                )
            except subprocess.TimeoutExpired:
                producer.terminate()
                try:
                    producer_stdout, producer_stderr = (
                        producer.communicate(timeout=10)
                    )
                except subprocess.TimeoutExpired:
                    producer.kill()
                    producer_stdout, producer_stderr = (
                        producer.communicate()
                    )

            producer_exit_code = producer.returncode

    print("\n[4] Producer outcome during outage:", flush=True)
    print(f"Exit code: {producer_exit_code}")
    print(producer_stdout)
    if producer_stderr:
        print(producer_stderr, file=sys.stderr)

    # A producer may either retry successfully or fail clearly.
    # Rerun the exact deterministic workload after recovery.
    print(
        "\n[5] Replaying the same 100 orders after recovery...",
        flush=True,
    )

    rerun = run_python(
        "scripts.produce_orders",
        "--limit",
        str(LIMIT),
        "--seed",
        str(SEED),
        timeout=180,
    )

    # All new messages must be persisted/acknowledged before
    # running the consumer.
    print("\n[6] Consuming recovered messages...", flush=True)

    consumer = run_python(
        "scripts.consume_orders",
        "--idle-seconds",
        "10",
        "--batch-size",
        "200",
        timeout=180,
    )

    print(
        "\n[7] Verifying order-status reconciliation...",
        flush=True,
    )

    run_python(
        "scripts.verify_stream_status",
        timeout=120,
    )

    after = db_snapshot()

    regressions = [
        order_id
        for order_id, old_rank in before["ranks"].items()
        if after["ranks"].get(order_id, -1) < old_rank
    ]

    checks = {
        "outage_observed": outage_observed,
        "broker_recovered": kafka_ready(),
        "rerun_succeeded": rerun.returncode == 0,
        "consumer_succeeded": consumer.returncode == 0,
        "no_duplicate_event_ids": after["duplicate_ids"] == 0,
        "no_status_regressions": not regressions,
        "event_count_not_decreased": (
            after["events"] >= before["events"]
        ),
        "current_count_not_decreased": (
            after["current"] >= before["current"]
        ),
    }

    verdict = (
        "TERTANGKAP"
        if all(checks.values())
        else "FAIL"
    )

    evidence = {
        "scenario": "F04_KAFKA_BROKER_OUTAGE",
        "started_at_utc": started_at,
        "finished_at_utc": (
            datetime.now(timezone.utc).isoformat()
        ),
        "orders_replayed": LIMIT,
        "seed": SEED,
        "delay_ms": DELAY_MS,
        "outage_seconds": OUTAGE_SECONDS,
        "producer_exit_during_outage": producer_exit_code,
        "producer_stdout_tail": producer_stdout[-3000:],
        "producer_stderr_tail": producer_stderr[-3000:],
        "db_before": {
            "events": before["events"],
            "current": before["current"],
        },
        "db_after": {
            "events": after["events"],
            "current": after["current"],
            "duplicate_ids": after["duplicate_ids"],
        },
        "status_regressions": len(regressions),
        "checks": checks,
        "verdict": verdict,
    }

    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== F04 RESULTS ===")
    print(f"Producer during outage exit: {producer_exit_code}")
    print(f"Kafka outage observed: {outage_observed}")
    print(f"Kafka recovered: {checks['broker_recovered']}")
    print(f"Events before: {before['events']:,}")
    print(f"Events after: {after['events']:,}")
    print(f"Duplicate event IDs: {after['duplicate_ids']}")
    print(f"Status regressions: {len(regressions)}")
    print(f"Evidence: {EVIDENCE}")
    print(f"F04 verdict: {verdict}")

    if verdict != "TERTANGKAP":
        raise AssertionError("F04 did not pass all checks")


if __name__ == "__main__":
    main()
