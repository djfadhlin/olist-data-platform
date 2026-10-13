"""Bronze ingestion untuk Olist Data Platform."""

import csv

import hashlib
import os
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv

import json
from datetime import datetime, timezone

from botocore.exceptions import ClientError


ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env")

RAW_DIR = ROOT / "data" / "raw"
BUCKET_NAME = "bronze"


def create_minio_client():
    """Membuat client S3 untuk MinIO."""

    endpoint = (
        f"http://localhost:"
        f"{os.environ['MINIO_API_PORT']}"
    )

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        region_name="us-east-1",
        config=Config(
            signature_version="s3v4",
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 2},
        ),
    )


def calculate_sha256(file_path: Path) -> str:
    """Menghitung SHA-256 tanpa memuat seluruh file ke memori."""

    digest = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def build_object_key(file_path: Path, checksum: str) -> str:
    """Membuat path objek yang bergantung pada isi file."""

    table_name = file_path.stem

    return (
        f"olist/{table_name}/"
        f"versions/sha256={checksum}/"
        f"{file_path.name}"
    )

def count_csv_rows(file_path: Path) -> int:
    """Menghitung record CSV tanpa menghitung header."""

    with file_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.reader(file)

        # Lewati header
        next(reader)

        return sum(1 for _ in reader)

def build_manifest(
    file_path: Path,
    checksum: str,
    row_count: int,
    previous_manifest: dict | None = None,
) -> dict:
    """Membuat manifest baru atau menambahkan versi baru."""

    size_bytes = file_path.stat().st_size
    object_key = build_object_key(file_path, checksum)

    # Jika sudah ada manifest, pertahankan riwayat sebelumnya.
    manifest = (
        previous_manifest.copy()
        if previous_manifest is not None
        else {
            "table": file_path.stem,
            "source_file": file_path.name,
            "versions": [],
        }
    )

    versions = list(manifest["versions"])

    # Jangan membuat versi tambahan jika checksum sudah tercatat.
    existing = next(
        (
            version
            for version in versions
            if version["sha256"] == checksum
        ),
        None,
    )

    if existing is None:
        versions.append({
            "sha256": checksum,
            "object_key": object_key,
            "size_bytes": size_bytes,
            "row_count": row_count,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        })

    manifest["versions"] = versions
    manifest["latest_sha256"] = checksum
    manifest["latest_object_key"] = object_key

    return manifest

def build_manifest_key(table_name: str) -> str:
    """Membuat lokasi manifest suatu tabel di MinIO."""

    return f"olist/{table_name}/manifest.json"


def read_manifest(client, table_name: str) -> dict | None:
    """Membaca manifest yang sudah tersimpan di bucket Bronze."""

    manifest_key = build_manifest_key(table_name)

    try:
        response = client.get_object(
            Bucket=BUCKET_NAME,
            Key=manifest_key,
        )

        content = response["Body"].read()

        return json.loads(content.decode("utf-8"))

    except ClientError as error:
        error_code = error.response["Error"]["Code"]

        # Manifest belum tersedia pada ingestion pertama.
        if error_code in ("NoSuchKey", "404"):
            return None

        # Error lain, seperti AccessDenied, tidak boleh disembunyikan.
        raise

def write_manifest(client, manifest: dict) -> None:
    """Menyimpan manifest JSON suatu tabel ke MinIO."""

    manifest_key = build_manifest_key(manifest["table"])

    payload = json.dumps(
        manifest,
        indent=2,
        ensure_ascii=False,
    ).encode("utf-8")

    client.put_object(
        Bucket=BUCKET_NAME,
        Key=manifest_key,
        Body=payload,
        ContentLength=len(payload),
        ContentType="application/json",
    )

def object_exists(client, object_key: str) -> bool:
    """Memeriksa apakah objek tersedia di bucket Bronze."""

    try:
        client.head_object(
            Bucket=BUCKET_NAME,
            Key=object_key,
        )
        return True

    except ClientError as error:
        error_code = error.response["Error"]["Code"]

        if error_code in ("404", "NoSuchKey", "NotFound"):
            return False

        # Jangan menyembunyikan error autentikasi atau server.
        raise

def upload_bronze_file(client, file_path: Path) -> dict:
    """Upload CSV ke Bronze tanpa menimpa versi yang sudah ada."""

    checksum = calculate_sha256(file_path)
    object_key = build_object_key(file_path, checksum)
    size_bytes = file_path.stat().st_size

    # 1. Periksa apakah objek sudah tersedia.
    if object_exists(client, object_key):
        response = client.head_object(
            Bucket=BUCKET_NAME,
            Key=object_key,
        )

        remote_checksum = response.get("Metadata", {}).get("sha256")
        remote_size = response["ContentLength"]

        if remote_checksum != checksum or remote_size != size_bytes:
            raise RuntimeError(
                f"Existing object verification failed: {file_path.name}"
            )

        print(f"Object already exists and verified: {object_key}")

        return {
            "status": "exists",
            "object_key": object_key,
            "sha256": checksum,
        }

    # 2. Objek belum tersedia: lakukan upload.
    with file_path.open("rb") as file:
        client.put_object(
            Bucket=BUCKET_NAME,
            Key=object_key,
            Body=file,
            ContentLength=size_bytes,
            ContentType="text/csv",
            Metadata={"sha256": checksum},
            IfNoneMatch="*",
        )

    # 3. Periksa hasil upload.
    response = client.head_object(
        Bucket=BUCKET_NAME,
        Key=object_key,
    )

    remote_checksum = response.get("Metadata", {}).get("sha256")
    remote_size = response["ContentLength"]

    if remote_checksum != checksum or remote_size != size_bytes:
        raise RuntimeError(
            f"Upload verification failed: {file_path.name}"
        )

    return {
        "status": "uploaded",
        "object_key": object_key,
        "sha256": checksum,
    }

def ingest_one_file(client, file_path: Path) -> dict:
    """Ingest satu CSV dan perbarui manifest Bronze."""

    table_name = file_path.stem
    checksum = calculate_sha256(file_path)

    # Baca riwayat versi yang sudah tercatat.
    previous_manifest = read_manifest(client, table_name)

    previous_versions = (
        previous_manifest.get("versions", [])
        if previous_manifest is not None
        else []
    )

    checksum_registered = any(
        version["sha256"] == checksum
        for version in previous_versions
    )

    # Upload atau verifikasi CSV terlebih dahulu.
    upload_result = upload_bronze_file(client, file_path)

    # Jika versi sudah tercatat dan objek valid,
    # ingestion tidak perlu mengubah manifest.
    if checksum_registered:
        if previous_manifest["latest_sha256"] != checksum:
            updated_manifest = build_manifest(
                file_path,
                checksum,
                count_csv_rows(file_path),
                previous_manifest,
            )
            write_manifest(client, updated_manifest)

        return {
            "table": table_name,
            "status": "unchanged",
            "object_key": upload_result["object_key"],
        }

    # Versi baru hanya dicatat setelah objek tersedia.
    row_count = count_csv_rows(file_path)

    updated_manifest = build_manifest(
        file_path,
        checksum,
        row_count,
        previous_manifest,
    )

    write_manifest(client, updated_manifest)

    status = (
        "uploaded"
        if previous_manifest is None
        else "new_version"
    )

    return {
        "table": table_name,
        "status": status,
        "object_key": upload_result["object_key"],
    }

def inspect_sources():
    """Memeriksa sumber dan menyiapkan metadata awal."""

    csv_files = sorted(RAW_DIR.glob("*.csv"))

    if len(csv_files) != 9:
        raise ValueError(
            f"Diharapkan 9 file CSV, ditemukan {len(csv_files)}"
        )

    for file_path in csv_files:
        checksum = calculate_sha256(file_path)
        object_key = build_object_key(file_path, checksum)
        row_count = count_csv_rows(file_path)

        print(f"\nDataset: {file_path.name}")
        print(f"Size: {file_path.stat().st_size:,} bytes")
        print(f"SHA-256: {checksum}")
        print(f"Object key: {object_key}")
        print(f"Rows: {row_count:,}")

def ingest_all_files() -> list[dict]:
    """Menjalankan Bronze ingestion untuk seluruh CSV."""

    csv_files = sorted(RAW_DIR.glob("*.csv"))

    if len(csv_files) != 9:
        raise ValueError(
            f"Diharapkan 9 CSV, ditemukan {len(csv_files)}"
        )

    client = create_minio_client()
    results = []

    for file_path in csv_files:
        print(f"\nProcessing: {file_path.name}")

        result = ingest_one_file(client, file_path)
        results.append(result)

        print(f"Status: {result['status']}")

    return results

if __name__ == "__main__":
    inspect_sources()

    # Uji pembuatan manifest menggunakan file orders.
    sample_file = RAW_DIR / "olist_orders_dataset.csv"

    sample_checksum = calculate_sha256(sample_file)
    sample_rows = count_csv_rows(sample_file)

    sample_manifest = build_manifest(
        sample_file,
        sample_checksum,
        sample_rows,
    )

    print("\n=== MANIFEST PREVIEW ===")
    print(json.dumps(sample_manifest, indent=2))

    print("\n=== REMOTE MANIFEST CHECK ===")

    client = create_minio_client()

    remote_manifest = read_manifest(
        client,
        "olist_orders_dataset",
    )

    print("Manifest exists:", remote_manifest is not None)

    if remote_manifest is not None:
        print("Existing versions:", len(remote_manifest["versions"]))

    print("\n=== REMOTE OBJECT CHECK ===")

    sample_key = build_object_key(
        sample_file,
        sample_checksum,
    )

    print(
        "Orders CSV exists:",
        object_exists(client, sample_key),
    )

    print("\n=== SINGLE FILE UPLOAD TEST ===")

    small_file = (
        RAW_DIR / "product_category_name_translation.csv"
    )

    upload_result = upload_bronze_file(
        client,
        small_file,
    )

    print("Status:", upload_result["status"])
    print("Object key:", upload_result["object_key"])
    print("SHA-256:", upload_result["sha256"])