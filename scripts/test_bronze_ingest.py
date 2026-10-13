from olist.bronze import (
    RAW_DIR,
    create_minio_client,
    ingest_one_file,
    read_manifest,
)


def main():
    client = create_minio_client()

    file_path = (
        RAW_DIR / "product_category_name_translation.csv"
    )

    print("=== BRONZE INGEST TEST ===")

    result = ingest_one_file(client, file_path)

    print("Table:", result["table"])
    print("Status:", result["status"])
    print("Object key:", result["object_key"])

    print("\n=== REMOTE MANIFEST CHECK ===")

    manifest = read_manifest(
        client,
        "product_category_name_translation",
    )

    if manifest is None:
        raise RuntimeError("Manifest tidak ditemukan di MinIO")

    print("Manifest exists:", True)
    print("Version count:", len(manifest["versions"]))
    print("Latest SHA-256:", manifest["latest_sha256"])
    print("Latest object:", manifest["latest_object_key"])


if __name__ == "__main__":
    main()