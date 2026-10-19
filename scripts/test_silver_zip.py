import pandas as pd

from olist.silver import parse_zip_prefix


def main():
    values = pd.Series(
        ["01310", "12345", "1234", "ABCDE", None],
        dtype="string",
    )

    result = parse_zip_prefix(values)

    print("=== ZIP PREFIX PARSING TEST ===")

    for original, parsed in zip(values, result):
        print(f"{original!r} -> {parsed!r}")

    assert result.iloc[0] == "01310"
    assert result.iloc[1] == "12345"
    assert pd.isna(result.iloc[2])
    assert pd.isna(result.iloc[3])
    assert pd.isna(result.iloc[4])

    print("\nZIP parsing test: PASS")


if __name__ == "__main__":
    main()