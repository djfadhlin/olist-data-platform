import pandas as pd

from olist.quality import check_h03_purchase_timestamp


def main():
    print("=== HARD RULE H03 TEST ===")

    source = pd.DataFrame({
        "order_purchase_timestamp": [
            "2018-01-15 13:45:00",
            "2018-02-30 10:00:00",
            None,
            "bukan-tanggal",
            "2017-12-31 23:59:59",
        ],
    })

    violations = check_h03_purchase_timestamp(source)

    print(violations.to_string(index=False))

    assert len(violations) == 3
    assert set(violations["source_row"]) == {1, 2, 3}
    assert set(violations["rule_id"]) == {"H03"}

    print("\nH03 test: PASS")


if __name__ == "__main__":
    main()