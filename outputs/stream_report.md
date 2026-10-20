# T3 — Kafka Streaming Report

Generated at: 2026-10-20T03:09:28.063962+00:00

## 1. Architecture

Kafka input topic: `olist.order_events`

Kafka DLQ topic: `olist.order_events.dlq`

Kafka consumer group: `olist-stream-consumer-v1`

PostgreSQL tables:

- `stream.order_events`
- `stream.order_current`
- `stream.order_dlq`

Processing design:

1. Producer generates order lifecycle events from raw Olist orders.
2. Kafka transports messages keyed by `order_id`.
3. Consumer validates event schema and timestamps.
4. Valid events are inserted with deterministic `event_id`.
5. Current order status is updated using status rank.
6. Invalid events are stored in Kafka DLQ and PostgreSQL DLQ.
7. Kafka offsets are committed manually after DB commit.

## 2. Full Replay Summary

| Metric | Value |
|---|---:|
| Source orders | 99,441 |
| Base events | 394,713 |
| Kafka messages acknowledged | 406,554 |
| Kafka messages consumed | 406,554 |
| Producer duration (seconds) | 50.17 |
| Consumer duration (seconds) | 528.17 |

## 3. Consumer Metrics

| Classification | Count |
|---|---:|
| New (reported counter) | 374,241 |
| Duplicate | 15,781 |
| Out of order | 14,558 |
| Dead-letter messages | 1,974 |

Important limitation:

The consumer's `new` counter is incorrect when
out-of-order events occur. The existing implementation
subtracts from `new` despite tracking out-of-order
separately. The reported counter must not be used as
an authoritative count of unique valid events.

Deduplication is enforced at database level using
the deterministic `event_id` primary key.

## 4. Freshness

| Metric | Result |
|---|---:|
| p50 freshness (ms) | 219,331.61 |
| p95 freshness (ms) | 442,934.87 |

Freshness measures the elapsed time between the event's
`produced_at` timestamp and consumption. Backlog affects
these results.

## 5. Fault Injection

Configured producer injection rates:

- Duplicate events: 3%
- Delayed events: 2%
- Corrupt messages: 0.5%

The replay produced 406,554
messages from 394,713
base lifecycle events.

Corrupt events were routed to both Kafka DLQ and
PostgreSQL DLQ.

## 6. Recovery and Status Reconciliation

Initial mismatched final statuses:
490

Recovery events successfully processed:

- First recovery: 365
- Second recovery: 125
- Total: 490

Recovery regenerated valid final events from PostgreSQL
raw source and republished them to Kafka. It did not
directly update the stream tables.

Final verification result:
**PASS**

```text
﻿=== T3 STREAM STATUS RECONCILIATION ===
Expected orders: 99,441
Loaded orders: 99,441
Missing orders: 0
Status mismatches: 0

T3 stream status reconciliation: PASS
```

## 7. Reliability and Known Limitations

- Kafka uses `acks=all` for producer acknowledgement.
- Event IDs are deterministic, enabling consumer deduplication.
- Kafka offsets are committed after the PostgreSQL transaction.
- Kafka DLQ publishing is not transactional with the database.
  A crash may therefore duplicate a message in the Kafka DLQ.
- PostgreSQL DLQ uses the source topic, partition and offset
  to deduplicate records.
- Final-status recovery is based on reconciliation with the
  batch raw source, not automated Kafka DLQ repair.
- The full consumer run was above the five-minute target.
  Further optimization and a measured rerun are needed.
- Controlled process-kill and broker-outage evidence is
  not yet included in this report.

## 8. Assessment

- Full source coverage: PASS.
- Producer acknowledgement: PASS.
- Kafka consumption: PASS.
- Corrupt message handling: PASS.
- Final status reconciliation after recovery:
  PASS.
- Under-five-minute full replay: NOT MET.
- Crash/restart failure tests: PENDING.
