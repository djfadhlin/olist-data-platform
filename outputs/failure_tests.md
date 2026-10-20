# T6 — Failure Injection Test Report

Generated UTC: 2026-10-20T17:17:15.264853+00:00

## Summary

| ID | Scenario | Verdict | Evidence source |
|---|---|---|---|
| F01 | Missing source CSV column | TERTANGKAP | Automated rerun |
| F02 | Duplicate Kafka producer | TERTANGKAP | Observed terminal output |
| F03 | Consumer crash before offset commit | TERTANGKAP | Observed terminal output |
| F04 | Kafka broker outage mid replay | TERTANGKAP | `f04_kafka_outage.json` |
| F05 | Full batch rerun | TERTANGKAP | `f05_batch_rerun.json` |

**Result: 5/5 observed scenarios passed.**

F02 and F03 results below are historical terminal observations,
not independently re-executed by this report generator.

## F01 — Missing CSV Column

- Injection: remove `order_id` from temporary orders CSV.
- Symptom: schema validator raises `ValueError`.
- Detection: required CSV header contract.
- Verdict: **TERTANGKAP**.
- Recovery: restore the required header; original CSV was never modified.

```text
=== SCHEMA DRIFT TEST ===
olist_customers_dataset: PASS (5 columns)
olist_geolocation_dataset: PASS (5 columns)
olist_order_items_dataset: PASS (7 columns)
olist_order_payments_dataset: PASS (5 columns)
olist_order_reviews_dataset: PASS (7 columns)
Schema drift detected: True
Missing order_id reported: True
Error: Schema drift pada olist_orders_dataset.csv: missing=['order_id'], unexpected=[], expected_order=['order_id', 'customer_id', 'order_status', 'order_purchase_timestamp', 'order_approved_at', 'order_delivered_carrier_date', 'order_delivered_customer_date', 'order_estimated_delivery_date'], actual_order=['customer_id', 'order_status', 'order_purchase_timestamp', 'order_approved_at', 'order_delivered_carrier_date', 'order_delivered_customer_date', 'order_estimated_delivery_date']
```

## F02 — Producer Executed Twice

- Injection: same first 20 orders produced twice using seed 42.
- Messages: 82 + 82 = **164**.
- Consumer duplicate classifications: **164**.
- `stream.order_events`: **393,251 before and after**.
- `stream.order_current`: **99,441 before and after**.
- DLQ: **1,996 before and after**.
- Duplicate `event_id`: **0**.
- Status regressions: **0**.
- Detection: `event_id` primary key and `ON CONFLICT DO NOTHING`.
- Recovery: idempotent consumer processes duplicates without extra rows.
- Verdict: **TERTANGKAP**.
- Source: F02 terminal output observed during project execution.

## F03 — Consumer Crash Before Offset Commit

- Injection: deliberate process exit code **73** after DB commit.
- Kafka partition: **0**.
- Offset immediately after crash: **136903**.
- Offset after restart: **136904**.
- Same Kafka message processed again after restart.
- Event rows before and after: **1**.
- Status regressions: **0**.
- Detection: explicitly recorded crash boundary and Kafka offset.
- Recovery: restart on same dedicated consumer group.
- Verdict: **TERTANGKAP**.
- Limitation: chosen event was already stored before the crash; this
  proves replay/deduplication but not first insertion before a crash.
- Source: F03 terminal output observed during project execution.

## F04 — Kafka Broker Outage

- Outage observed: **True**.
- Producer exit during outage: **1**.
- Symptom: `KafkaConnectionError: socket disconnected`.
- Broker recovered: **True**.
- Events before: **393,251**.
- Events after: **393,251**.
- Duplicate event IDs: **0**.
- Status regressions: **0**.
- Recovery: restart Kafka, replay identical workload, consume,
  and reconcile all order statuses with Raw.
- Verdict: **TERTANGKAP**.
- Evidence: `outputs/f04_kafka_outage.json`.

## F05 — Full Batch Rerun

- Injection: rerun Bronze, Silver, Raw, DW and Gold without
  changing the source CSVs.
- Detection: source checksums, Bronze version manifest,
  Silver logical row hashes, and PostgreSQL fingerprints.
- `source`: **PASS**.
- `bronze`: **PASS**.
- `silver`: **PASS**.
- `postgres`: **PASS**.
- Silver rows: **1,550,922**.
- Stream reconciliation after rerun: **0 missing, 0 mismatches**.
- Combined DW and mart tests: **55 passed**.
- Recovery: repeat the batch with unchanged inputs and verify
  the same published datasets.
- Verdict: **TERTANGKAP**.
- Evidence: `outputs/f05_batch_rerun.json`.

## Limitations

- F02 and F03 measurements were captured in terminal output;
  separate machine-readable JSON artifacts were not recorded.
- F03 used an event already stored before injection.
- F05 excludes `soft_quality_flags.parquet` from its nine-table
  logical data comparison.
- F05 database fingerprints exclude selected volatile audit columns.
- A successful retry after a broker outage does not demonstrate
  high availability: the Kafka deployment has one broker.
