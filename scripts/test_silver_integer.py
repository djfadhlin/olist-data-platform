import pandas as pd

from olist.silver import parse_integer


def main():
    values = pd.Series(
        ["10", "0", "-2", "2.5", "ABC", None],
        dtype="string",
    )

    result = parse_integer(values)

    print("=== INTEGER PARSING TEST ===")

    for original, parsed in zip(values, result):
        print(f"{original!r} -> {parsed!r}")

    assert result.iloc[0] == 10
    assert result.iloc[1] == 0
    assert result.iloc[2] == -2
    assert pd.isna(result.iloc[3])
    assert pd.isna(result.iloc[4])
    assert pd.isna(result.iloc[5])
    assert str(result.dtype) == "Int64"

    print("\nInteger parsing test: PASS")


if __name__ == "__main__":
    main()