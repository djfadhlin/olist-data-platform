import pandas as pd

from olist.quality import check_h05_item_amounts


def main():
    print("=== HARD RULE H05 TEST ===")

    source = pd.DataFrame({
        "price": [
            "100.00",
            "-5.00",
            "ABC",
            "20.00",
            "12.345",
        ],
        "freight_value": [
            "10.00",
            "5.00",
            "3.00",
            None,
            "-2.00",
        ],
    })

    violations = check_h05_item_amounts(source)

    print(violations.to_string(index=False))

    assert len(violations) == 5
    assert set(violations["source_row"]) == {1, 2, 3, 4}
    assert set(violations["rule_id"]) == {"H05"}

    # Baris 4 melanggar aturan pada kedua kolom.
    assert (
        (violations["source_row"] == 4).sum() == 2
    )

    print("\nH05 test: PASS")


if __name__ == "__main__":
    main()