from olist.bronze import (
    RAW_DIR,
    build_object_key,
    calculate_sha256,
    create_minio_client,
    object_exists,
    read_manifest,
)


def main():
    client = create_minio_client()
    csv_files = sorted(RAW_DIR.glob("*.csv"))

    print("=== BRONZE MANIFEST VERIFICATION ===")

    all_valid = True

    for file_path in csv_files:
        manifest = read_manifest(client, file_path.stem)

        if manifest is None:
            print(f"{file_path.stem}: MISSING MANIFEST")
            all_valid = False
            continue

        local_sha256 = calculate_sha256(file_path)
        expected_key = build_object_key(file_path, local_sha256)

        versions = manifest["versions"]

        # Semua versi harus memiliki objek di MinIO.
        all_objects_exist = all(
            object_exists(client, version["object_key"])
            for version in versions
        )

        # Versi asli harus tercatat.
        original_registered = any(
            version["sha256"] == local_sha256
            for version in versions
        )

        # Latest harus menunjuk CSV asli.
        latest_valid = (
            manifest["latest_sha256"] == local_sha256
            and manifest["latest_object_key"] == expected_key
        )

        expected_versions = (
            2
            if file_path.stem == "product_category_name_translation"
            else 1
        )

        valid = (
            len(versions) == expected_versions
            and all_objects_exist
            and original_registered
            and latest_valid
        )

        status = "PASS" if valid else "FAIL"

        print(
            f"{file_path.stem}: "
            f"versions={len(versions)}, "
            f"latest_original={latest_valid}, "
            f"all_objects_exist={all_objects_exist}, "
            f"status={status}"
        )

        if not valid:
            all_valid = False

    print("\nAll manifests valid:", all_valid)

    if not all_valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()