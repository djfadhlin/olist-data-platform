
"""Upload artefak Silver yang telah diverifikasi ke MinIO."""

import os
from pathlib import Path

import boto3
from dotenv import load_dotenv

from olist.schema import TABLE_SCHEMAS


SILVER_DIR = Path("outputs/silver")
BUCKET = "silver"
PREFIX = "olist"


def main():
    print("=== UPLOAD SILVER TO MINIO ===")

    load_dotenv()

    port = os.getenv("MINIO_API_PORT", "9000")
    access_key = os.environ["MINIO_ROOT_USER"]
    secret_key = os.environ["MINIO_ROOT_PASSWORD"]

    client = boto3.client(
        "s3",
        endpoint_url=f"http://localhost:{port}",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
    )

    expected_files = [
        f"{name}.parquet"
        for name in TABLE_SCHEMAS
    ] + [
        "soft_quality_flags.parquet",
        "dq_report.md",
    ]

    # Validasi semua file lokal sebelum upload.
    for filename in expected_files:
        path = SILVER_DIR / filename

        if not path.is_file():
            raise FileNotFoundError(path)

    # Pastikan bucket tersedia.
    buckets = {
        item["Name"]
        for item in client.list_buckets()["Buckets"]
    }

    if BUCKET not in buckets:
        client.create_bucket(Bucket=BUCKET)

    for filename in expected_files:
        path = SILVER_DIR / filename
        object_key = f"{PREFIX}/{filename}"

        client.upload_file(
            str(path),
            BUCKET,
            object_key,
        )

        # Verifikasi ukuran hasil upload.
        metadata = client.head_object(
            Bucket=BUCKET,
            Key=object_key,
        )

        if metadata["ContentLength"] != path.stat().st_size:
            raise RuntimeError(
                f"Ukuran upload tidak cocok: {filename}"
            )

        print(
            f"PASS: s3://{BUCKET}/{object_key} "
            f"({path.stat().st_size:,} bytes)"
        )

    print(f"\nUploaded objects: {len(expected_files)}")
    print("Silver MinIO upload: PASS")


if __name__ == "__main__":
    main()
