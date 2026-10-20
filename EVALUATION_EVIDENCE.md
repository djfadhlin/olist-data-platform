# EVALUATION EVIDENCE — Olist Data Platform

Generated UTC: 2026-10-20T17:17:15.572578+00:00

## 1. Executive Summary

Pipeline: CSV → Bronze MinIO → Silver Parquet → PostgreSQL Raw → DW Star Schema → Gold Marts.

Kafka handles order lifecycle replay separately, with PostgreSQL event deduplication and a dead-letter queue.

- Source datasets: **9**.
- Source rows: **1,550,922**.
- Silver rows: **1,550,922**.
- Quarantine: **0**.
- Soft-quality flags: **13,344**.
- DW integrity violations: **0**.
- Failure injection: **5/5 TERTANGKAP**.

The pipeline meets the tested correctness and recovery checks. The original full streaming consumer run did **not** meet the under-five-minute performance target.

## 2. Stage Durations

### Latest recorded build durations

| Stage | Duration | Source |
|---|---|---|
| Bronze latest ingestion | 0.60 s | outputs/bronze_report.md |
| PostgreSQL Raw load | 6.71 s | outputs/load_report.md |
| Kafka producer full replay | 50.17 s | outputs/stream_report.md |
| Kafka consumer full replay | 528.17 s | outputs/stream_report.md |
| DW build | 8.14 s | outputs/dw_report.md |
| Gold Marts build | 3.47 s | outputs/marts_report.md |

These durations belong to different recorded runs. They should not be added together as a single end-to-end pipeline benchmark.

### F05 full-batch rerun

| Stage | Duration | Exit code |
|---|---|---|
| Bronze | 4.86 s | 0 |
| Silver | 40.94 s | 0 |
| Raw | 9.37 s | 0 |
| DW | 11.35 s | 0 |
| Gold Marts | 6.27 s | 0 |

Total F05 CLI stage duration: **72.79 s**.

This total measures the recorded Bronze, Silver, Raw, DW and Gold commands; it excludes F05 snapshot hashing and its additional verification commands.

## 3. Rows per Layer

| Layer | Dataset/table count | Rows |
|---|---|---|
| Source / Bronze | 9 | 1,550,922 |
| Silver main datasets | 9 | 1,550,922 |
| Silver quarantine | — | 0 |
| PostgreSQL Raw | 9 | 1,550,922 |

### Data Warehouse tables

| Table | Rows |
|---|---|
| dw.dim_date | 1,827 |
| dw.dim_customer | 96,096 |
| dw.dim_product | 32,951 |
| dw.dim_seller | 3,095 |
| dw.dim_geo | 18,677 |
| dw.fact_order | 99,441 |
| dw.fact_order_item | 112,650 |
| dw.fact_payment | 103,886 |
| dw.fact_review | 98,673 |

### Gold Mart tables

| Mart | Rows |
|---|---|
| mart.monthly_sales | 11,670 |
| mart.delivery_performance | 565 |
| mart.seller_scorecard | 3,095 |
| mart.customer_rfm | 96,096 |
| mart.stream_freshness | 13 |
| mart.payment_reconciliation | 99,441 |

Do not sum DW fact and dimension counts into a single business-row count: their grains differ.

## 4. Data Quality Gate

- Source: **1,550,922** rows.
- Silver: **1,550,922** rows.
- Quarantine: **0** rows.
- Soft flags: **13,344**.
- Quality threshold: **1% quarantine per table**.
- Final publication gate: **PASS**.

Soft flags do not remove rows; multiple flags may refer to the same source record.

### Soft-rule counts

| Rule | Flags |
|---|---|
| S01 | 8 |
| S02 | 23 |
| S03 | 0 |
| S04 | 11,687 |
| S05 | 547 |
| S06 | 775 |
| S07 | 1 |
| S08 | 303 |

## 5. Kafka Streaming Reliability and Performance

| Metric | Value |
|---|---|
| Source orders | 99,441 |
| Base lifecycle events | 394,713 |
| Messages produced | 406,554 |
| Messages consumed | 406,554 |
| Producer full replay | 50.17 s |
| Consumer full replay | 528.17 s |
| Freshness p50 | 219,331.61 ms |
| Freshness p95 | 442,934.87 ms |

Final source-to-stream order status reconciliation: **99,441 orders loaded, 0 missing, 0 mismatches**, as recorded in `outputs/stream_report.md`.

The historical streaming report records an incorrect `new` consumer classification counter when out-of-order events occurred. It is not used as an authoritative unique-event count here.

**Performance verdict:** original full consumer replay was above the five-minute target. Broker-outage recovery and duplicate handling passed subsequent focused failure tests, but those tests are not a replacement full replay benchmark.

## 6. DW Integrity

- Integrity checks: **20**.
- Total reported violations: **0**.

### Reconciliation details

| Metric | Value |
|---|---|
| orders_without_items | 775 |
| orders_without_payments | 1 |
| orders_with_reviews | 98,673 |
| unknown_customer_geo | 1,357 |
| unknown_seller_geo | 14 |
| multi_review_orders | 547 |
| delivered_orders | 96,478 |

## 7. Business Questions Q1–Q4

### Q1 — Revenue Trend and Categories

Peak reported month: **2017-11-01**, product revenue **BRL 987765.37**.

Top category: **health_beauty**, product revenue **BRL 1229557.50**.

Revenue uses delivered-order item prices; freight is reported separately. Business analysis uses complete months January 2017 through August 2018.

### Q2 — Delivery Performance

Evaluable orders: **96203**.

Late orders: **6531**.

Late rate: **6.79%**.

Mean review score ON_TIME: **4.291**; LATE: **2.271**.

This is an observed association, not evidence that late delivery alone caused the review difference.

### Q3 — Seller Scorecard

Highest reported eligible seller: `4869f7a5dfa277a7dca6462dcf3b52b2`.

Delivered product revenue: **BRL 226987.93**.

Seller rankings require at least 30 evaluable orders. Orders with multiple sellers can share the same order-level review score.

### Q4 — Customer RFM

AT_RISK customers: **53810**.

AT_RISK monetary value: **BRL 7337773.83**.

RFM recency is anchored to the latest delivered-order purchase date plus one day, not the current wall-clock date.

## 8. Payment Reconciliation

Total orders: **99441**.

Matched orders: **98362**.

Match rate: **98.915%**.

Unmatched absolute difference: **BRL 166004.63**.

Unexplained-class absolute difference: **BRL 78.87**.

### Reconciliation classes

| Class | Orders | Absolute difference (BRL) |
|---|---|---|
| MATCH | 98362 | 2.73 |
| NO_ITEMS | 775 | 162591.95 |
| INSTALLMENT_REVIEW | 266 | 3172.87 |
| UNEXPLAINED | 30 | 78.87 |
| VOUCHER_REVIEW | 7 | 17.48 |
| NO_PAYMENT | 1 | 143.46 |

The non-UNEXPLAINED classifications describe possible mismatch causes; they do not prove accounting adjustments.

## 9. Failure Injection Results

| Case | Scenario | Verdict | Evidence |
|---|---|---|---|
| F01 | Missing source CSV column | TERTANGKAP | Automated rerun |
| F02 | Duplicate Kafka producer | TERTANGKAP | Observed terminal output |
| F03 | Consumer crash before offset commit | TERTANGKAP | Observed terminal output |
| F04 | Kafka broker outage mid replay | TERTANGKAP | f04_kafka_outage.json |
| F05 | Full batch rerun | TERTANGKAP | f05_batch_rerun.json |

F04 broker outage observed: **True**; broker recovered: **True**.

F05 source, Bronze, Silver and PostgreSQL fingerprints unchanged: **True**.

F02 and F03 use observed historical terminal evidence. F03 used an event already stored before the injected crash.

See `outputs/failure_tests.md` for detection mechanisms, symptoms and recovery details.

## 10. Architecture Decision Table

| Decision | Chosen design | Rejected alternative | Reason |
|---|---|---|---|
| Bronze storage | Content-addressed MinIO with SHA-256 | Overwrite a single CSV object | Preserve source versions and support rerun verification |
| Silver processing | Pandas/Parquet with quality gates | Silent row dropping | Preserve reconciliation and expose hard/soft violations |
| Raw load | Transactional TRUNCATE + COPY | Append rows on every rerun | Prevent duplicates and roll back failed loads |
| Kafka semantics | Manual offsets + deterministic event_id | Auto commit before DB persistence | Support replay after a crash without duplicate DB rows |
| Customer dimension | SCD Type 1 | Full Type 2 history | Simpler person-grain analytics, with known history loss |
| Warehouse | Explicit star-schema grains and foreign keys | One wide joined table | Avoid join multiplication and support reusable dimensions |
| Gold layer | Materialized PostgreSQL marts + CSV exports | Notebook-only aggregation | Reusable queries, validation, and easier audit |

## 11. Limitations

1. Full Kafka consumer replay exceeded the five-minute target.
2. Kafka is deployed as a single broker; there is no broker failover.
3. Kafka DLQ publication and PostgreSQL commit are not one distributed transaction.
4. The historical T3 `new` metric is not authoritative due to the counter bug.
5. F03 proves offset recovery and deduplication for an already-stored event, not first-time insertion before crash.
6. F05 excludes the auxiliary `soft_quality_flags.parquet` from its nine-dataset content comparison and excludes certain audit columns from database fingerprints.
7. Customer SCD Type 1 does not preserve historical customer attributes.
8. Payment mismatch labels are hypotheses for investigation, not proven causes.

## 12. Next Experiments

1. Optimize consumer batching and retry behavior, then repeat the complete 99,441-order replay and measure the under-five-minute target.
2. Run a controlled crash test with a brand-new event committed to PostgreSQL before Kafka offset commit.
3. Extend F05 comparison to soft-quality flags and audit-column changes.
4. Evaluate Kafka multi-broker deployment and realistic failover behavior.
5. Investigate installment/voucher reconciliation cases with transaction-level evidence.

## 13. Evidence Lineage

| Source artifact | Purpose |
|---|---|
| outputs/bronze_report.md | Source inventory, versions, ingest duration |
| outputs/silver/dq_report.md | Quality gates, soft flags, row counts |
| outputs/load_report.md | Raw transaction and load timing |
| outputs/stream_report.md | Historical full Kafka replay and reconciliation |
| outputs/dw_report.md | Star-schema counts and integrity |
| outputs/marts_report.md | Gold counts and Q1–Q4 results |
| outputs/failure_tests.md | Failure injection results |
| outputs/f04_kafka_outage.json | Machine-readable broker-outage evidence |
| outputs/f05_batch_rerun.json | Machine-readable full-batch rerun evidence |
| notebooks/olist_t5_dashboard.ipynb | Executed dashboard notebook |

All numeric evaluation values above are derived from the corresponding report artifacts or failure-test JSON. Decision rationales, caveats and next experiments are engineering interpretations.
