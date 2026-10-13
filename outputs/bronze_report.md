# Bronze Ingestion Report

Generated at: 2026-10-13T09:55:03.319791+00:00

## Dataset Inventory

| Dataset | Rows (latest) | Size (bytes) | Versions | Latest SHA-256 |
|---|---:|---:|---:|---|
| olist_customers_dataset | 99,441 | 9,133,399 | 1 | `8a80cdbd27b4...` |
| olist_geolocation_dataset | 1,000,163 | 62,274,047 | 1 | `3b7cf4f504ce...` |
| olist_order_items_dataset | 112,650 | 15,551,322 | 1 | `14e321c489a7...` |
| olist_order_payments_dataset | 103,886 | 5,881,025 | 1 | `6ca92718f7e0...` |
| olist_order_reviews_dataset | 99,224 | 14,451,670 | 1 | `012b61c7593e...` |
| olist_orders_dataset | 99,441 | 17,754,356 | 1 | `1dca8c9a7a8d...` |
| olist_products_dataset | 32,951 | 2,412,398 | 1 | `66f99d026119...` |
| olist_sellers_dataset | 3,095 | 177,799 | 1 | `c877ee451aad...` |
| product_category_name_translation | 71 | 2,613 | 2 | `a81f0d1f27b2...` |

## Summary

- Total datasets: 9
- Total rows (latest versions): 1,550,922
- Total bytes (latest versions): 127,638,629
- Storage: MinIO / bucket `bronze`
- Versioning: content-addressed using SHA-256
- CSV objects: append-only
- Manifest: version history with latest pointer

## Ingestion Test Results

| Test | Result |
|---|---|
| Initial batch ingestion | 8 uploaded, 1 unchanged |
| Initial batch duration | 3.25 seconds |
| Second batch ingestion | 9 unchanged |
| Second batch duration | 0.54 seconds |
| One-byte modification | new_version |
| Previous version preserved | PASS |
| Latest restored to original | PASS |
| Final manifest validation | 9/9 PASS |

Note: The translation dataset was uploaded separately
before the initial batch ingestion.
