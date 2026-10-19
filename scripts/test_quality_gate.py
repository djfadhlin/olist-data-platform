
from decimal import Decimal

from olist.quality_gate import evaluate_quality_gate


def main():
    print("=== QUALITY GATE TEST ===")

    clean = evaluate_quality_gate(
        source_rows=1000,
        quarantine_rows=0,
    )
    assert clean["verdict"] == "PASS"
    print("No quarantine: PASS")

    acceptable = evaluate_quality_gate(
        source_rows=1000,
        quarantine_rows=10,
    )
    assert acceptable["verdict"] == "PASS+KARANTINA"
    assert acceptable["quarantine_rate"] == Decimal("0.01")
    print("Exactly 1% quarantine: PASS")

    failed = evaluate_quality_gate(
        source_rows=1000,
        quarantine_rows=11,
    )
    assert failed["verdict"] == "FAIL"
    print("Above 1% quarantine: PASS")

    empty = evaluate_quality_gate(
        source_rows=0,
        quarantine_rows=0,
    )
    assert empty["verdict"] == "PASS"
    print("Empty dataset: PASS")

    try:
        evaluate_quality_gate(10, 11)
    except ValueError:
        print("Invalid counts rejected: PASS")
    else:
        raise AssertionError("Invalid counts must raise ValueError")

    print("\nQuality gate test: PASS")


if __name__ == "__main__":
    main()
