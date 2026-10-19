
import pandas as pd

from olist.soft_quality import check_geolocation_soft_rules


def main():
    print("=== SOFT RULE S04 TEST ===")

    source = pd.DataFrame({
        "geolocation_lat": [
            -23.55,
            10.0,
            -25.0,
            -40.0,
            -15.0,
        ],
        "geolocation_lng": [
            -46.63,
            -46.0,
            -80.0,
            -80.0,
            -50.0,
        ],
    })

    violations = check_geolocation_soft_rules(source)

    print(violations.to_string(index=False))

    assert len(violations) == 3
    assert set(violations["source_row"]) == {1, 2, 3}
    assert set(violations["rule_id"]) == {"S04"}

    # Soft rule hanya membuat flag; tidak menghapus record.
    assert len(source) == 5

    print("\nS04 test: PASS")


if __name__ == "__main__":
    main()
