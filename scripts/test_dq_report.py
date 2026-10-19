
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from olist.dq_report import write_dq_report


def main():
    print("=== DQ REPORT TEST ===")

    summary = {
        "table_a": {
            "source_rows": 200,
            "silver_rows": 199,
            "quarantine_rows": 1,
            "quarantine_rate": 0.005,
            "verdict": "PASS+KARANTINA",
        },
        "table_b": {
            "source_rows": 100,
            "silver_rows": 100,
            "quarantine_rows": 0,
            "quarantine_rate": 0.0,
            "verdict": "PASS",
        },
    }

    soft_flags = pd.DataFrame({
        "rule_id": ["S01", "S01", "S04", "S08"],
    })

    with TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "dq_report.md"

        write_dq_report(summary, soft_flags, path)

        assert path.exists()

        content = path.read_text(encoding="utf-8")

        assert "PASS+KARANTINA" in content
        assert "Source rows: **300**" in content
        assert "Silver rows: **299**" in content
        assert "Quarantine rows: **1**" in content
        assert "| S01 | 2 |" in content
        assert "| S04 | 1 |" in content
        assert "| S08 | 1 |" in content
        assert "| S03 | 0 |" in content

        print(content)

    print("\nDQ report test: PASS")


if __name__ == "__main__":
    main()