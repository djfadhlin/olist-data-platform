
"""Quality gate untuk menentukan PASS, PASS+KARANTINA, atau FAIL."""

from decimal import Decimal


QUARANTINE_THRESHOLD = Decimal("0.01")


def evaluate_quality_gate(
    source_rows: int,
    quarantine_rows: int,
    threshold: Decimal = QUARANTINE_THRESHOLD,
) -> dict:
    """Evaluasi persentase karantina dalam satu tabel."""

    if source_rows < 0:
        raise ValueError("source_rows tidak boleh negatif")

    if quarantine_rows < 0 or quarantine_rows > source_rows:
        raise ValueError("quarantine_rows harus berada dalam 0..source_rows")

    if not Decimal("0") <= threshold <= Decimal("1"):
        raise ValueError("threshold harus berada dalam 0..1")

    if source_rows == 0:
        return {
            "source_rows": 0,
            "quarantine_rows": 0,
            "quarantine_rate": Decimal("0"),
            "threshold": threshold,
            "verdict": "PASS",
        }

    rate = Decimal(quarantine_rows) / Decimal(source_rows)

    if quarantine_rows == 0:
        verdict = "PASS"
    elif rate <= threshold:
        verdict = "PASS+KARANTINA"
    else:
        verdict = "FAIL"

    return {
        "source_rows": source_rows,
        "quarantine_rows": quarantine_rows,
        "quarantine_rate": rate,
        "threshold": threshold,
        "verdict": verdict,
    }
