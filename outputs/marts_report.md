# T5 - Olist Gold Marts Report

Generated (UTC): 2026-10-20T09:32:41.848751+00:00

Build duration: 6.72 seconds

## Mart row counts

| Mart | Rows |
|---|---:|
| `mart.monthly_sales` | 11,670 |
| `mart.delivery_performance` | 565 |
| `mart.seller_scorecard` | 3,095 |
| `mart.customer_rfm` | 96,096 |
| `mart.stream_freshness` | 13 |
| `mart.payment_reconciliation` | 99,441 |

## Q1 - Monthly product revenue (BRL)

| month_start | product_revenue_brl | freight_brl | item_count |
| --- | --- | --- | --- |
| 2017-01-01 | 111798.36 | 15684.01 | 913 |
| 2017-02-01 | 234223.40 | 37015.92 | 1858 |
| 2017-03-01 | 359198.85 | 55132.10 | 2897 |
| 2017-04-01 | 340669.68 | 50142.72 | 2569 |
| 2017-05-01 | 489338.25 | 77513.15 | 4004 |
| 2017-06-01 | 421923.37 | 68127.00 | 3489 |
| 2017-07-01 | 481604.52 | 84694.56 | 4416 |
| 2017-08-01 | 554699.70 | 91132.66 | 4797 |
| 2017-09-01 | 607399.67 | 93677.82 | 4737 |
| 2017-10-01 | 648247.65 | 102869.36 | 5214 |
| 2017-11-01 | 987765.37 | 165598.83 | 8475 |
| 2017-12-01 | 726033.19 | 117045.10 | 6187 |
| 2018-01-01 | 924645.00 | 153242.46 | 8037 |
| 2018-02-01 | 826437.13 | 139731.28 | 7518 |
| 2018-03-01 | 953356.25 | 167241.99 | 8017 |
| 2018-04-01 | 973534.09 | 159344.84 | 7827 |
| 2018-05-01 | 977544.69 | 151229.83 | 7810 |
| 2018-06-01 | 856077.86 | 155900.43 | 7010 |
| 2018-07-01 | 867953.46 | 159853.82 | 6963 |
| 2018-08-01 | 838576.64 | 146915.00 | 7142 |

## Q1 - Top 10 categories

| category | product_revenue_brl | item_count |
| --- | --- | --- |
| health_beauty | 1229557.50 | 9422 |
| watches_gifts | 1163465.91 | 5855 |
| bed_bath_table | 1022955.77 | 10945 |
| sports_leisure | 952840.40 | 8414 |
| computers_accessories | 888055.59 | 7632 |
| furniture_decor | 706237.17 | 8095 |
| housewares | 614341.62 | 6783 |
| cool_stuff | 609158.00 | 3711 |
| auto | 577838.39 | 4132 |
| garden_tools | 469135.40 | 4263 |

## Q2 - Delivery late rate

| delivered_orders | evaluable_orders | late_orders | late_rate_pct |
| --- | --- | --- | --- |
| 96211 | 96203 | 6531 | 6.79 |

## Q2 - Review score vs lateness

| delivery_group | reviewed_orders | avg_review_score |
| --- | --- | --- |
| LATE | 6378 | 2.271 |
| ON_TIME | 89182 | 4.291 |

## Q3 - Top 10 eligible sellers

| seller_id | seller_state | delivered_orders | evaluable_orders | late_orders | late_rate_pct | avg_review_score | delivered_product_revenue_brl |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4869f7a5dfa277a7dca6462dcf3b52b2 | SP | 1124 | 1124 | 118 | 10.50 | 4.133 | 226987.93 |
| 53243585a1d6dc2643021fd1853d8905 | BA | 348 | 348 | 12 | 3.45 | 4.132 | 217940.44 |
| 4a3ca9315b744ce9f8e9374361493884 | SP | 1772 | 1772 | 172 | 9.71 | 3.828 | 196882.12 |
| fa1c13f2614d7b5c4749cbc52fecda94 | SP | 578 | 578 | 53 | 9.17 | 4.339 | 190917.14 |
| 7c67e1448b00f6e969d365cea6b010ab | SP | 973 | 973 | 89 | 9.15 | 3.489 | 186570.05 |
| 7e93a43ef30c4f03f38b393420bc753a | SP | 319 | 319 | 15 | 4.70 | 4.215 | 165981.49 |
| da8622b14eb17ae2831f4ac5b9dab84a | SP | 1311 | 1311 | 87 | 6.64 | 4.176 | 159816.87 |
| 7a67c85e85bb2ce8582c35f2203ad736 | SP | 1145 | 1145 | 60 | 5.24 | 4.245 | 139658.69 |
| 1025f0e2d44d7041d6cf58b6550e0bfa | SP | 910 | 910 | 72 | 7.91 | 3.990 | 138208.56 |
| 955fee9216a65b617aa5c0531780ce60 | SP | 1261 | 1261 | 77 | 6.11 | 4.157 | 131836.71 |

## Q4 - Customer RFM segments

| segment | customers | delivered_orders | monetary_brl | avg_recency_days |
| --- | --- | --- | --- | --- |
| AT_RISK | 53810 | 53810 | 7337773.83 | 339.15 |
| REGULAR | 18968 | 18968 | 2697940.33 | 136.65 |
| RECENT | 17779 | 17779 | 2457375.20 | 45.21 |
| NO_DELIVERED_ORDER | 2738 | 0 | 0.00 | NULL |
| LOYAL | 2190 | 4599 | 563538.66 | 269.53 |
| CHAMPIONS | 611 | 1322 | 164870.09 | 46.19 |

## Streaming freshness overview

| valid_unique_events | observed_minutes | first_minute | last_minute | negative_latency_events |
| --- | --- | --- | --- | --- |
| 393251 | 13 | 2026-10-20 02:07:00+00:00 | 2026-10-20 03:00:00+00:00 | 0 |

## Payment reconciliation by class

| reconciliation_class | orders | absolute_difference_brl | signed_difference_brl |
| --- | --- | --- | --- |
| MATCH | 98362 | 2.73 | -0.67 |
| NO_ITEMS | 775 | 162591.95 | 162591.95 |
| INSTALLMENT_REVIEW | 266 | 3172.87 | 2927.73 |
| UNEXPLAINED | 30 | 78.87 | -74.15 |
| VOUCHER_REVIEW | 7 | 17.48 | 17.48 |
| NO_PAYMENT | 1 | 143.46 | -143.46 |

## Payment reconciliation match rate

| total_orders | matched_orders | match_rate_pct | unmatched_absolute_difference_brl | unexplained_absolute_difference_brl |
| --- | --- | --- | --- | --- |
| 99441 | 98362 | 98.915 | 166004.63 | 78.87 |

## Business definitions

- Revenue is the sum of item `price` for orders with status `delivered`.
- Freight is reported separately from product revenue.
- Monthly sales and delivery performance use the purchase month.
- Complete months: January 2017 through August 2018.
- Late rate uses only orders with `is_late IS NOT NULL`.
- Each order has at most one selected review in `dw.fact_review`.
- Seller ranking requires at least 30 evaluable orders.
- RFM recency uses the latest delivered-order purchase date plus one day.
- RFM frequency uses fixed thresholds, not raw quintiles.
- Reconciliation tolerance is BRL 0.01.
- Voucher and installment mismatch classes require further investigation.

## Limitations

- Revenue excludes non-delivered orders by business definition.
- Seller ratings reflect order-level reviews shared across sellers when an order has multiple sellers.
- Freshness uses valid unique events stored in PostgreSQL, not every Kafka message consumed.
- The current streaming event table does not explicitly identify replay batches.
- Financial mismatch classes indicate possible causes, not proven accounting adjustments.

## Source lineage

- `raw.*` -> `dw.*` -> `mart.*` -> `outputs/gold/*.csv`.
- `stream.order_events` -> `mart.stream_freshness`.
- Shared report and dashboard queries: `olist/mart_queries.py`.
