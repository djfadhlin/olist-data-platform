from pathlib import Path
from tempfile import TemporaryDirectory

from olist.bronze import (
    RAW_DIR,
    calculate_sha256,
    create_minio_client,
    read_manifest,
    ingest_one_file,
    object_exists,
)


def main():
    source = RAW_DIR / "product_category_name_translation.csv"

    original_checksum = calculate_sha256(source)
    client = create_minio_client()

    print("=== BEFORE VERSIONING TEST ===")

    before = read_manifest(client, source.stem)

    if before is None:
        raise RuntimeError("Manifest awal belum tersedia")

    old_key = before["latest_object_key"]

    print("Versions before:", len(before["versions"]))
    print("Original SHA-256:", original_checksum)

    # Buat salinan sementara dengan nama file yang sama.
    with TemporaryDirectory() as temp_dir:
        test_file = Path(temp_dir) / source.name

        # Baca byte asli, lalu ubah tepat satu byte
        # di bagian akhir file.
        original_bytes = source.read_bytes()

        if not original_bytes:
            raise RuntimeError("File sumber kosong")

        modified = bytearray(original_bytes)
        modified[-1] = (
            ord("X") if modified[-1] != ord("X") else ord("Y")
        )

        test_file.write_bytes(modified)

        new_checksum = calculate_sha256(test_file)

        print("\n=== MODIFIED COPY ===")
        print("Checksum changed:", new_checksum != original_checksum)
        print("Original unchanged:", calculate_sha256(source) == original_checksum)

        # Ingest salinan yang berubah ke tabel yang sama.
        result = ingest_one_file(client, test_file)

        print("\n=== VERSIONING RESULT ===")
        print("Status:", result["status"])

        after = read_manifest(client, source.stem)

        print("Versions after:", len(after["versions"]))
        print("Old object exists:", object_exists(client, old_key))
        print(
            "New object exists:",
            object_exists(client, after["latest_object_key"]),
        )


if __name__ == "__main__":
    main()