import csv
from pathlib import Path
from tempfile import TemporaryDirectory

from olist.schema import validate_csv_headers


def main():
    print("=== SCHEMA DRIFT TEST ===")

    with TemporaryDirectory() as temp_dir:
        raw_dir = Path(temp_dir)

        # Buat header sesuai kontrak untuk seluruh tabel.
        from olist.schema import TABLE_SCHEMAS

        for table_name, spec in TABLE_SCHEMAS.items():
            file_path = raw_dir / f"{table_name}.csv"

            with file_path.open(
                "w",
                encoding="utf-8",
                newline="",
            ) as file:
                writer = csv.writer(file)
                writer.writerow(
                    [column.name for column in spec.columns]
                )

        # Simulasikan kolom order_id yang hilang.
        orders_path = raw_dir / "olist_orders_dataset.csv"

        with orders_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as file:
            writer = csv.writer(file)
            writer.writerow([
                column.name
                for column in TABLE_SCHEMAS[
                    "olist_orders_dataset"
                ].columns
                if column.name != "order_id"
            ])

        try:
            validate_csv_headers(raw_dir)

        except ValueError as error:
            message = str(error)

            print("Schema drift detected:", True)
            print("Missing order_id reported:", "order_id" in message)
            print("Error:", message)

            assert "order_id" in message

        else:
            raise AssertionError(
                "Validator gagal mendeteksi kolom order_id yang hilang"
            )


if __name__ == "__main__":
    main()