import os
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

# Membaca konfigurasi proyek
load_dotenv(ROOT / ".env")

endpoint = f"http://localhost:{os.environ['MINIO_API_PORT']}"

client = boto3.client(
    "s3",
    endpoint_url=endpoint,
    aws_access_key_id=os.environ["MINIO_ROOT_USER"],
    aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
    region_name="us-east-1",
    config=Config(
        signature_version="s3v4",
        connect_timeout=5,
        read_timeout=10,
        retries={"max_attempts": 1},
    ),
)

print("=== MINIO CONNECTION CHECK ===")
print(f"Endpoint: {endpoint}")

response = client.list_buckets()

bucket_names = [
    bucket["Name"]
    for bucket in response.get("Buckets", [])
]

print("Connection: SUCCESS")
print("Existing buckets:", bucket_names)
print("Bronze bucket exists:", "bronze" in bucket_names)

print("\n=== BRONZE BUCKET CONTENTS ===")

if "bronze" in bucket_names:
    response = client.list_objects_v2(
        Bucket="bronze",
        MaxKeys=20,
    )

    objects = response.get("Contents", [])

    print("Bucket empty:", len(objects) == 0)

    for obj in objects:
        print(
            f"Object: {obj['Key']} | "
            f"Size: {obj['Size']:,} bytes"
        )

    print("More objects exist:", response.get("IsTruncated", False))