# T2 PostgreSQL Raw Load Report

Generated UTC: 2026-10-19T22:25:38.848726+00:00

## Load Configuration

- Source: `outputs/silver/*.parquet`
- Destination: PostgreSQL schema `raw`
- Method: `TRUNCATE + COPY FROM STDIN`
- Transaction: one transaction for all tables
- Failure behavior: rollback

## Table Load Summary

| Table | Loaded Rows | Status |
|---|---:|---|
| olist_customers_dataset | 99,441 | PASS |
| olist_geolocation_dataset | 1,000,163 | PASS |
| olist_order_items_dataset | 112,650 | PASS |
| olist_order_payments_dataset | 103,886 | PASS |
| olist_order_reviews_dataset | 99,224 | PASS |
| olist_orders_dataset | 99,441 | PASS |
| olist_products_dataset | 32,951 | PASS |
| olist_sellers_dataset | 3,095 | PASS |
| product_category_name_translation | 71 | PASS |

## Overall Result

- Tables loaded: **9**
- Total loaded rows: **1,550,922**
- Duration: **6.59 seconds**
- Row reconciliation: **PASS**
- Transaction committed: **YES**
