# T2 Data Quality Report

Generated UTC: 2026-10-19T22:09:47.650129+00:00

## Overall Result

- Verdict: **PASS**
- Quarantine threshold: **1% per table**
- Source rows: **1,550,922**
- Silver rows: **1,550,922**
- Quarantine rows: **0**
- Soft quality flags: **13,344**

## Row Reconciliation

- Source: 1,550,922
- Silver + Quarantine: 1,550,922 + 0
- Reconciliation: **PASS**

## Table Quality Summary

| Table | Source | Silver | Quarantine | Rate | Verdict |
|---|---:|---:|---:|---:|---|
| olist_customers_dataset | 99,441 | 99,441 | 0 | 0.000% | PASS |
| olist_geolocation_dataset | 1,000,163 | 1,000,163 | 0 | 0.000% | PASS |
| olist_order_items_dataset | 112,650 | 112,650 | 0 | 0.000% | PASS |
| olist_order_payments_dataset | 103,886 | 103,886 | 0 | 0.000% | PASS |
| olist_order_reviews_dataset | 99,224 | 99,224 | 0 | 0.000% | PASS |
| olist_orders_dataset | 99,441 | 99,441 | 0 | 0.000% | PASS |
| olist_products_dataset | 32,951 | 32,951 | 0 | 0.000% | PASS |
| olist_sellers_dataset | 3,095 | 3,095 | 0 | 0.000% | PASS |
| product_category_name_translation | 71 | 71 | 0 | 0.000% | PASS |

## Hard Rule Counts

| Rule | Violation Count |
|---|---:|
| H01 | 0 |
| H02 | 0 |
| H03 | 0 |
| H04 | 0 |
| H05 | 0 |
| H06 | 0 |
| H07 | 0 |
| H08 | 0 |
| H09 | 0 |
| H10 | 0 |
| SCHEMA | 0 |

Hard-rule counts represent violation events, not unique quarantined rows.

One source row may violate multiple rules, but it is quarantined only once.

## Soft Rule Counts

| Rule | Flag Count |
|---|---:|
| S01 | 8 |
| S02 | 23 |
| S03 | 0 |
| S04 | 11,687 |
| S05 | 547 |
| S06 | 775 |
| S07 | 1 |
| S08 | 303 |

Soft-rule flags do not remove Silver records.

## Quality Gate Policy

Quarantine threshold: **1% per table**.

- **PASS**: zero quarantined rows.
- **PASS+KARANTINA**: quarantine rate > 0% and <= 1%.
- **FAIL**: quarantine rate > 1%.

The threshold is calculated separately for each table so that a small but broken dataset is not hidden by larger datasets such as Geolocation.

If any table fails its quality gate, the complete new Silver batch is not published.
