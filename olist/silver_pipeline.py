
"""Pipeline Silver Parquet dengan Data Quality Gate.

Tahapan:
1. Validasi header CSV.
2. Parsing berdasarkan schema.
3. Validasi Hard Rules H01-H10 dan SCHEMA.
4. Karantina record bermasalah.
5. Quality gate 1% per tabel.
6. Validasi Soft Rules S01-S08.
7. Penulisan Silver dan Soft Flags Parquet.
8. Pembuatan laporan Data Quality.
9. Publikasi lokal dengan directory swap.

Belum mengunggah data ke MinIO atau PostgreSQL.
"""

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pandas as pd

from olist.dq_report import build_dq_report
from olist.quality import collect_all_hard_violations
from olist.quality_gate import evaluate_quality_gate
from olist.schema import TABLE_SCHEMAS, validate_csv_headers
from olist.silver import (
    parse_table,
    quarantine_parse_failures,
)
from olist.soft_quality import run_all_soft_rules


HARD_RULE_IDS = [
    *[f"H{i:02d}" for i in range(1, 11)],
    "SCHEMA",
]


def prepare_silver(
    raw_dir: Path,
    output_dir: Path,
) -> dict:
    """Validasi, proses, dan publikasikan Silver secara lokal.

    Semua dataset disiapkan di staging terlebih dahulu.
    Jika satu tabel gagal quality gate, output sebelumnya
    tetap dipertahankan.
    """

    raw_dir = Path(raw_dir)
    output_dir = Path(output_dir)

    # =====================================================
    # 1. VALIDASI HEADER SELURUH CSV
    # =====================================================

    # Schema drift harus terdeteksi sebelum pemrosesan.
    validate_csv_headers(raw_dir)

    # =====================================================
    # 2. PEMROSESAN DI STAGING
    # =====================================================

    with TemporaryDirectory() as temp_dir:
        staging_dir = Path(temp_dir)

        summary = {}
        gate_failed = False
        silver_tables = {}

        # Hitung pelanggaran setiap Hard Rule dan SCHEMA.
        hard_rule_counts = {
            rule_id: 0 for rule_id in HARD_RULE_IDS
        }

        for table_name in TABLE_SCHEMAS:
            csv_path = raw_dir / f"{table_name}.csv"

            # Seluruh kolom dibaca sebagai string.
            # Tipe final mengikuti schema.py.
            source = pd.read_csv(
                csv_path,
                dtype="string",
                encoding="utf-8-sig",
                keep_default_na=False,
            )

            parsed = parse_table(
                source,
                table_name,
            )

            # Validasi Hard Rules dan aturan schema.
            violations = collect_all_hard_violations(
                source,
                parsed,
                table_name,
            )

            # Akumulasi jumlah pelanggaran per rule_id.
            if not violations.empty:
                counts = violations.groupby("rule_id").size()

                for rule_id, count in counts.items():
                    hard_rule_counts[rule_id] = (
                        hard_rule_counts.get(rule_id, 0)
                        + int(count)
                    )

            # Pisahkan Silver dan karantina.
            silver, quarantine = quarantine_parse_failures(
                source,
                parsed,
                violations,
                table_name,
            )

            # Dipakai oleh Soft Rules lintas tabel.
            # Indeks asli tidak di-reset.
            silver_tables[table_name] = silver

            # Quality gate per tabel.
            gate = evaluate_quality_gate(
                source_rows=len(source),
                quarantine_rows=len(quarantine),
            )

            summary[table_name] = {
                "source_rows": len(source),
                "silver_rows": len(silver),
                "quarantine_rows": len(quarantine),
                "violations": len(violations),
                "verdict": gate["verdict"],
                "quarantine_rate": float(
                    gate["quarantine_rate"]
                ),
            }

            # Validasi rekonsiliasi record.
            if len(source) != len(silver) + len(quarantine):
                raise AssertionError(
                    f"Row reconciliation failed: {table_name}"
                )

            if gate["verdict"] == "FAIL":
                gate_failed = True

            # Silver Parquet.
            silver.to_parquet(
                staging_dir / f"{table_name}.parquet",
                engine="pyarrow",
                index=False,
            )

            # Karantina disimpan hanya bila ada record bermasalah.
            if not quarantine.empty:
                quarantine.to_parquet(
                    staging_dir / f"{table_name}_quarantine.parquet",
                    engine="pyarrow",
                    index=False,
                )

            print(
                f"{table_name}: "
                f"source={len(source):,}, "
                f"silver={len(silver):,}, "
                f"quarantine={len(quarantine):,}, "
                f"verdict={gate['verdict']}"
            )

        # =====================================================
        # 3. QUALITY GATE KESELURUHAN BATCH
        # =====================================================

        if gate_failed:
            raise RuntimeError(
                "Quality gate FAIL: Silver tidak dipublikasikan."
            )

        # =====================================================
        # 4. SOFT RULES S01-S08
        # =====================================================

        # Soft Rules mencatat flag tanpa menghapus record.
        soft_flags = run_all_soft_rules(silver_tables)

        soft_flags.to_parquet(
            staging_dir / "soft_quality_flags.parquet",
            engine="pyarrow",
            index=False,
        )

        soft_counts = (
            soft_flags.groupby("rule_id").size().to_dict()
            if not soft_flags.empty
            else {}
        )

        print("\n=== SOFT QUALITY SUMMARY ===")

        for rule_id in (
            "S01", "S02", "S03", "S04",
            "S05", "S06", "S07", "S08",
        ):
            print(
                f"{rule_id}: "
                f"{soft_counts.get(rule_id, 0):,}"
            )

        print(
            f"Total soft flags: {len(soft_flags):,}"
        )

        # =====================================================
        # 5. LAPORAN DATA QUALITY
        # =====================================================

        report_content = build_dq_report(
            summary=summary,
            soft_flags=soft_flags,
            hard_rule_counts=hard_rule_counts,
        )

        report_path = staging_dir / "dq_report.md"

        report_path.write_text(
            report_content,
            encoding="utf-8",
        )

        # =====================================================
        # 6. PUBLIKASI LOKAL DENGAN DIRECTORY SWAP
        # =====================================================

        output_dir.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Direktori generasi baru dan backup dibuat
        # sejajar dengan folder final.
        new_dir = output_dir.with_name(
            f"{output_dir.name}.new-{uuid4().hex}"
        )

        backup_dir = output_dir.with_name(
            f"{output_dir.name}.backup-{uuid4().hex}"
        )

        try:
            # Siapkan seluruh artefak generasi baru.
            shutil.copytree(
                staging_dir,
                new_dir,
            )

            had_previous = output_dir.exists()

            # Simpan generasi sebelumnya sebagai backup.
            if had_previous:
                output_dir.rename(backup_dir)

            try:
                # Pasang generasi baru ke lokasi output.
                new_dir.rename(output_dir)

            except Exception:
                # Pulihkan output sebelumnya jika gagal.
                if had_previous and backup_dir.exists():
                    backup_dir.rename(output_dir)

                raise

            # Hapus backup setelah publikasi berhasil.
            if backup_dir.exists():
                shutil.rmtree(backup_dir)

        finally:
            # Hapus generasi baru bila masih tertinggal.
            if new_dir.exists():
                shutil.rmtree(new_dir)

        print("\n=== SILVER PUBLICATION ===")
        print(f"Output directory: {output_dir}")
        print("Publication: SUCCESS")

        return summary
