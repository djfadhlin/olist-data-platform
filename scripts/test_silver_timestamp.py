import pandas as pd

from olist.silver import parse_timestamp


def main():
    values = pd.Series(
        [
            "2018-01-15 13:45:00",
            "2017-12-31 23:59:59",
            "2018-02-30 10:00:00",
            "bukan-tanggal",
            None,
        ],
        dtype="string",
    )

    result = parse_timestamp(values)

    print("=== TIMESTAMP PARSING TEST ===")

    for original, parsed in zip(values, result):
        print(f"{original!r} -> {parsed!r}")

    assert result.iloc[0] == pd.Timestamp("2018-01-15 13:45:00")
    assert result.iloc[1] == pd.Timestamp("2017-12-31 23:59:59")
    assert pd.isna(result.iloc[2])
    assert pd.isna(result.iloc[3])
    assert pd.isna(result.iloc[4])
    assert pd.api.types.is_datetime64_any_dtype(result.dtype)

    print("\nTimestamp parsing test: PASS")


if __name__ == "__main__":
    main()