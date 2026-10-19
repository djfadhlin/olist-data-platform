from olist.bronze import RAW_DIR
from olist.schema import TABLE_SCHEMAS, validate_csv_headers


def main():
    print("=== SILVER SCHEMA CHECK ===")

    validate_csv_headers(RAW_DIR)

    total_columns = sum(
        len(spec.columns)
        for spec in TABLE_SCHEMAS.values()
    )

    print(f"\nTables: {len(TABLE_SCHEMAS)}")
    print(f"Columns: {total_columns}")
    print("Schema validation: PASS")


if __name__ == "__main__":
    main()