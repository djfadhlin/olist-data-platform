
"""Generate T6 failure injection report from recorded evidence.

Run:
    python -B -m scripts.generate_failure_report

F01 is rerun in a temporary directory.
F02/F03 use previously observed terminal evidence.
F04/F05 are read from machine-generated JSON files.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "outputs"
REPORT = OUTPUT / "failure_tests.md"


def read_json(filename):
    path = OUTPUT / filename

    if not path.is_file():
        raise FileNotFoundError(f"Missing evidence: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def run_f01():
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "scripts.test_schema_drift",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )

    output = result.stdout + result.stderr

    passed = (
        result.returncode == 0
        and "Schema drift detected: True" in output
        and "Missing order_id reported: True" in output
    )

    if not passed:
        raise AssertionError(
            "F01 schema drift test failed:\n" + output
        )

    return output


def main():
    print("=== T6 FAILURE REPORT GENERATOR ===")

    f01_output = run_f01()
    f04 = read_json("f04_kafka_outage.json")
    f05 = read_json("f05_batch_rerun.json")

    for name, evidence in (
        ("F04", f04),
        ("F05", f05),
    ):
        if evidence.get("verdict") != "TERTANGKAP":
            raise AssertionError(
                f"{name} evidence does not show PASS"
            )

    if not all(f04.get("checks", {}).values()):
        raise AssertionError("F04 has failing checks")

    if not all(f05.get("checks", {}).values()):
        raise AssertionError("F05 has failing checks")

    lines = [
        "# T6 — Failure Injection Test Report",
        "",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        "",
        "| ID | Scenario | Verdict | Evidence source |",
        "|---|---|---|---|",
        "| F01 | Missing source CSV column | TERTANGKAP | Automated rerun |",
        "| F02 | Duplicate Kafka producer | TERTANGKAP | Observed terminal output |",
        "| F03 | Consumer crash before offset commit | TERTANGKAP | Observed terminal output |",
        "| F04 | Kafka broker outage mid replay | TERTANGKAP | `f04_kafka_outage.json` |",
        "| F05 | Full batch rerun | TERTANGKAP | `f05_batch_rerun.json` |",
        "",
        "**Result: 5/5 observed scenarios passed.**",
        "",
        "F02 and F03 results below are historical terminal observations,",
        "not independently re-executed by this report generator.",
        "",
        "## F01 — Missing CSV Column",
        "",
        "- Injection: remove `order_id` from temporary orders CSV.",
        "- Symptom: schema validator raises `ValueError`.",
        "- Detection: required CSV header contract.",
        "- Verdict: **TERTANGKAP**.",
        "- Recovery: restore the required header; original CSV was never modified.",
        "",
        "```text",
        f01_output.strip(),
        "```",
        "",
        "## F02 — Producer Executed Twice",
        "",
        "- Injection: same first 20 orders produced twice using seed 42.",
        "- Messages: 82 + 82 = **164**.",
        "- Consumer duplicate classifications: **164**.",
        "- `stream.order_events`: **393,251 before and after**.",
        "- `stream.order_current`: **99,441 before and after**.",
        "- DLQ: **1,996 before and after**.",
        "- Duplicate `event_id`: **0**.",
        "- Status regressions: **0**.",
        "- Detection: `event_id` primary key and `ON CONFLICT DO NOTHING`.",
        "- Recovery: idempotent consumer processes duplicates without extra rows.",
        "- Verdict: **TERTANGKAP**.",
        "- Source: F02 terminal output observed during project execution.",
        "",
        "## F03 — Consumer Crash Before Offset Commit",
        "",
        "- Injection: deliberate process exit code **73** after DB commit.",
        "- Kafka partition: **0**.",
        "- Offset immediately after crash: **136903**.",
        "- Offset after restart: **136904**.",
        "- Same Kafka message processed again after restart.",
        "- Event rows before and after: **1**.",
        "- Status regressions: **0**.",
        "- Detection: explicitly recorded crash boundary and Kafka offset.",
        "- Recovery: restart on same dedicated consumer group.",
        "- Verdict: **TERTANGKAP**.",
        "- Limitation: chosen event was already stored before the crash; this",
        "  proves replay/deduplication but not first insertion before a crash.",
        "- Source: F03 terminal output observed during project execution.",
        "",
        "## F04 — Kafka Broker Outage",
        "",
        f"- Outage observed: **{f04['checks']['outage_observed']}**.",
        f"- Producer exit during outage: **{f04['producer_exit_during_outage']}**.",
        "- Symptom: `KafkaConnectionError: socket disconnected`.",
        f"- Broker recovered: **{f04['checks']['broker_recovered']}**.",
        f"- Events before: **{f04['db_before']['events']:,}**.",
        f"- Events after: **{f04['db_after']['events']:,}**.",
        f"- Duplicate event IDs: **{f04['db_after']['duplicate_ids']}**.",
        f"- Status regressions: **{f04['status_regressions']}**.",
        "- Recovery: restart Kafka, replay identical workload, consume,",
        "  and reconcile all order statuses with Raw.",
        f"- Verdict: **{f04['verdict']}**.",
        "- Evidence: `outputs/f04_kafka_outage.json`.",
        "",
        "## F05 — Full Batch Rerun",
        "",
        "- Injection: rerun Bronze, Silver, Raw, DW and Gold without",
        "  changing the source CSVs.",
        "- Detection: source checksums, Bronze version manifest,",
        "  Silver logical row hashes, and PostgreSQL fingerprints.",
    ]

    for check, passed in f05["checks"].items():
        lines.append(
            f"- `{check}`: **{'PASS' if passed else 'FAIL'}**."
        )

    lines.extend([
        f"- Silver rows: **{f05['silver_total_rows']:,}**.",
        "- Stream reconciliation after rerun: **0 missing, 0 mismatches**.",
        "- Combined DW and mart tests: **55 passed**.",
        "- Recovery: repeat the batch with unchanged inputs and verify",
        "  the same published datasets.",
        f"- Verdict: **{f05['verdict']}**.",
        "- Evidence: `outputs/f05_batch_rerun.json`.",
        "",
        "## Limitations",
        "",
        "- F02 and F03 measurements were captured in terminal output;",
        "  separate machine-readable JSON artifacts were not recorded.",
        "- F03 used an event already stored before injection.",
        "- F05 excludes `soft_quality_flags.parquet` from its nine-table",
        "  logical data comparison.",
        "- F05 database fingerprints exclude selected volatile audit columns.",
        "- A successful retry after a broker outage does not demonstrate",
        "  high availability: the Kafka deployment has one broker.",
        "",
    ])

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print("F01 automated rerun: PASS")
    print("F02 historical terminal evidence: PASS")
    print("F03 historical terminal evidence: PASS")
    print("F04 JSON evidence: PASS")
    print("F05 JSON evidence: PASS")
    print(f"Report: {REPORT}")
    print("T6 failure report: GENERATED")


if __name__ == "__main__":
    main()
