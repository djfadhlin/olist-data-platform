
"""Generator laporan Data Quality untuk T2 Olist Data Platform."""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


HARD_RULE_IDS = [
    *[f"H{i:02d}" for i in range(1, 11)],
    "SCHEMA",
]

SOFT_RULE_IDS = [
    f"S{i:02d}" for i in range(1, 9)
]


def build_dq_report(
    summary: dict,
    soft_flags: pd.DataFrame,
    hard_rule_counts: dict | None = None,
) -> str:
    """Bangun laporan Markdown dari hasil pipeline Silver."""

    hard_rule_counts = hard_rule_counts or {}

    # =====================================================
    # 1. TOTAL DATA DAN REKONSILIASI
    # =====================================================

    total_source = sum(
        item["source_rows"]
        for item in summary.values()
    )

    total_silver = sum(
        item["silver_rows"]
        for item in summary.values()
    )

    total_quarantine = sum(
        item["quarantine_rows"]
        for item in summary.values()
    )

    if total_source != total_silver + total_quarantine:
        raise ValueError(
            "DQ report reconciliation failed: "
            "source != silver + quarantine"
        )

    # =====================================================
    # 2. OVERALL QUALITY VERDICT
    # =====================================================

    failed_tables = [
        name
        for name, item in summary.items()
        if item["verdict"] == "FAIL"
    ]

    if failed_tables:
        overall_verdict = "FAIL"
    elif total_quarantine > 0:
        overall_verdict = "PASS+KARANTINA"
    else:
        overall_verdict = "PASS"

    # =====================================================
    # 3. SOFT RULE COUNTS
    # =====================================================

    soft_counts = (
        soft_flags.groupby("rule_id").size().to_dict()
        if not soft_flags.empty
        else {}
    )

    # =====================================================
    # 4. HEADER LAPORAN
    # =====================================================

    lines = [
        "# T2 Data Quality Report",
        "",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Overall Result",
        "",
        f"- Verdict: **{overall_verdict}**",
        "- Quarantine threshold: **1% per table**",
        f"- Source rows: **{total_source:,}**",
        f"- Silver rows: **{total_silver:,}**",
        f"- Quarantine rows: **{total_quarantine:,}**",
        f"- Soft quality flags: **{len(soft_flags):,}**",
        "",
        "## Row Reconciliation",
        "",
        f"- Source: {total_source:,}",
        f"- Silver + Quarantine: "
        f"{total_silver:,} + {total_quarantine:,}",
        "- Reconciliation: **PASS**",
        "",
    ]

    # =====================================================
    # 5. TABLE QUALITY SUMMARY
    # =====================================================

    lines.extend([
        "## Table Quality Summary",
        "",
        "| Table | Source | Silver | Quarantine | Rate | Verdict |",
        "|---|---:|---:|---:|---:|---|",
    ])

    for table_name, item in summary.items():
        rate = item["quarantine_rate"] * 100

        lines.append(
            f"| {table_name} | "
            f"{item['source_rows']:,} | "
            f"{item['silver_rows']:,} | "
            f"{item['quarantine_rows']:,} | "
            f"{rate:.3f}% | "
            f"{item['verdict']} |"
        )

    # =====================================================
    # 6. HARD RULE COUNTS H01-H10 + SCHEMA
    # =====================================================

    lines.extend([
        "",
        "## Hard Rule Counts",
        "",
        "| Rule | Violation Count |",
        "|---|---:|",
    ])

    for rule_id in HARD_RULE_IDS:
        count = hard_rule_counts.get(rule_id, 0)

        lines.append(
            f"| {rule_id} | {count:,} |"
        )

    lines.extend([
        "",
        "Hard-rule counts represent violation events, "
        "not unique quarantined rows.",
        "",
        "One source row may violate multiple rules, "
        "but it is quarantined only once.",
    ])

    # =====================================================
    # 7. SOFT RULE COUNTS S01-S08
    # =====================================================

    lines.extend([
        "",
        "## Soft Rule Counts",
        "",
        "| Rule | Flag Count |",
        "|---|---:|",
    ])

    for rule_id in SOFT_RULE_IDS:
        count = soft_counts.get(rule_id, 0)

        lines.append(
            f"| {rule_id} | {count:,} |"
        )

    lines.extend([
        "",
        "Soft-rule flags do not remove Silver records.",
    ])

    # =====================================================
    # 8. QUALITY GATE POLICY
    # =====================================================

    lines.extend([
        "",
        "## Quality Gate Policy",
        "",
        "Quarantine threshold: **1% per table**.",
        "",
        "- **PASS**: zero quarantined rows.",
        "- **PASS+KARANTINA**: quarantine rate > 0% and <= 1%.",
        "- **FAIL**: quarantine rate > 1%.",
        "",
        "The threshold is calculated separately for each table "
        "so that a small but broken dataset is not hidden "
        "by larger datasets such as Geolocation.",
        "",
        "If any table fails its quality gate, the complete "
        "new Silver batch is not published.",
        "",
    ])

    # =====================================================
    # 9. FAILED TABLES
    # =====================================================

    if failed_tables:
        lines.extend([
            "## Failed Tables",
            "",
        ])

        for table_name in failed_tables:
            lines.append(f"- {table_name}")

        lines.append("")

    # =====================================================
    # 10. RETURN MARKDOWN CONTENT
    # =====================================================

    return "\n".join(lines)


def write_dq_report(
    summary: dict,
    soft_flags: pd.DataFrame,
    output_path: Path,
    hard_rule_counts: dict | None = None,
) -> Path:
    """Tulis laporan Data Quality ke file Markdown."""

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    content = build_dq_report(
        summary=summary,
        soft_flags=soft_flags,
        hard_rule_counts=hard_rule_counts,
    )

    output_path.write_text(
        content,
        encoding="utf-8",
    )

    return output_path
