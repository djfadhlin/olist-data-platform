# T4 - Olist Data Warehouse Report

Generated at: 2026-10-20T03:37:42.918045+00:00

Build duration: 9.29 seconds

## Row counts

| Table | Rows |
|---|---:|
| `dw.dim_date` | 1,827 |
| `dw.dim_customer` | 96,096 |
| `dw.dim_product` | 32,951 |
| `dw.dim_seller` | 3,095 |
| `dw.dim_geo` | 18,677 |
| `dw.fact_order` | 99,441 |
| `dw.fact_order_item` | 112,650 |
| `dw.fact_payment` | 103,886 |
| `dw.fact_review` | 98,673 |

## Grain and integrity tests

| Test | Violations |
|---|---:|
| Missing customer reference | 0 |
| Missing customer geo reference | 0 |
| Missing seller geo reference | 0 |
| Missing order item reference | 0 |
| Missing item product reference | 0 |
| Missing item seller reference | 0 |
| Missing payment order reference | 0 |
| Missing review order reference | 0 |
| Duplicate customer grain | 0 |
| Duplicate order grain | 0 |
| Duplicate item grain | 0 |
| Duplicate payment grain | 0 |
| Duplicate review grain | 0 |
| Invalid late flag for undelivered orders | 0 |
| Incorrect late flag for delivered orders | 0 |
| Invalid Brazil coordinates | 0 |
| Missing English product category | 0 |
| Invalid review count | 0 |
| Incorrect item-missing flags | 0 |
| Incorrect payment-missing flags | 0 |

## Reconciliation metrics

| Metric | Value |
|---|---:|
| orders_without_items | 775 |
| orders_without_payments | 1 |
| orders_with_reviews | 98,673 |
| unknown_customer_geo | 1,357 |
| unknown_seller_geo | 14 |
| multi_review_orders | 547 |
| delivered_orders | 96,478 |

## Modeling decisions

- `dim_customer`: one row per `customer_unique_id`, using latest order attributes (SCD Type 1).
- `dim_geo`: one row per valid Brazilian ZIP prefix; `UNKNOWN` for unmatched locations.
- `dim_product`: corrected source column spelling and translated category with fallback.
- `fact_order`: includes orders without items or payments, with explicit flags.
- `fact_review`: one review per order, selected by latest answer timestamp, then creation timestamp, then review ID; original review count retained.
- `is_late`: NULL for non-delivered orders or missing delivery/estimate dates; date-based comparison.
- `dim_date.is_complete_month`: January 2017 through August 2018 inclusive.
- Full rebuild is idempotent because the warehouse is recreated from unchanged raw tables within one database transaction.
- SCD Type 1 does not retain historical changes in customer attributes.

## Result

**T4 database validation: PASS**
