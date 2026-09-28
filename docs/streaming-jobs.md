# The streaming job designs: API, sink mode, watermark and lateness

**Ticket:** [The streaming job designs](https://github.com/SoongGuanLeong/de-platform/issues/13)
**Map:** [Vendor-neutral lakehouse data platform: architecture proposal](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Target posting:** ONL Biz Solutions, Senior Data Engineer - Data Lakehouse ([JobStreet 94703893](https://my.jobstreet.com/job/94703893)), cached verbatim at `~/projects/career-ops/data/jd-cache/031.md`.
**Decisions recorded here:** [ADR-0013](adr/0013-lsn-ordering-in-a-stateful-operator.md), [ADR-0014](adr/0014-ripe-content-hash-and-backfill-producer.md) and [ADR-0015](adr/0015-serving-feed-as-its-own-job.md), resting on [ADR-0002](adr/0002-exactly-once-effect-not-delivery.md), [ADR-0008](adr/0008-two-spines-with-no-cross-domain-join.md), [ADR-0011](adr/0011-flink-native-iceberg-sink-for-cdc.md) and [ADR-0012](adr/0012-flink-writes-the-serving-copy.md).

---

## 1. What this document is

The job design for the platform's two streaming sources. It settles the API per job, the Iceberg sink configuration, the watermark and lateness policy, which sources are genuinely streaming rather than replayed batch, the state and checkpoint tuning plan, and the deduplication and idempotency design. It resolves [the streaming-jobs ticket](https://github.com/SoongGuanLeong/de-platform/issues/13) on the map, and it is the per-table detail [the technology-selection ticket](https://github.com/SoongGuanLeong/de-platform/issues/8) left open in ADR-0011.

It is a design, not a result. No throughput, checkpoint duration or latency figure appears. Every number is a budget or a plan, and the tuning record's numbers are produced later under the evidence standard in the requirements matrix. Every figure measured on TPC-C or TPC-H data is labelled a TPC-derived result and never a TPC Benchmark Result ([ADR-0009](adr/0009-dataset-licence-position-and-obligations.md)).

## 2. The three jobs

The CDC path is two jobs, so that a ClickHouse failure cannot stop ingestion (ADR-0015). The network path is one job.

| Job | Source | API | Writes | Ordering token | Idempotency |
|---|---|---|---|---|---|
| CDC ingestion | Debezium CDC on Kafka (TPC-C) | Flink DataStream, Java | Iceberg gold facts, upsert | `source.lsn`, enforced by a stateful operator | max-LSN operator, then the sink's checkpoint-id |
| CDC serving | the same Kafka topic | Flink SQL | ClickHouse `ReplacingMergeTree`, versioned by LSN | `source.lsn` | the engine's version collapse |
| RIPE ingestion | RIPE Atlas WebSocket, plus a REST backfill producer | Flink SQL | Iceberg raw results and a per-minute probe aggregate, upsert | event time, the probe timestamp | a content-hash key, and the window key |

## 3. Which sources are streaming and which are backfill

- **TPC-C via Debezium is genuinely streaming.** Real binlog change events, at-least-once on failover, the only T1 source.
- **The RIPE Atlas WebSocket is genuinely streaming, and at-most-once.** The server buffers and drops under backpressure with no redelivery.
- **The RIPE Atlas REST path is a backfill, and is labelled one.** It is a producer into the same Kafka topic, not a stream and not a second writer. It is the correctness path for any gap the live feed drops.
- **TPC-H and ONSPD are batch.** Neither has a streaming path, and neither appears in these jobs.

## 4. The CDC job

### 4.1 The API

DataStream, in Java. The ordering operator has no keyed-state equivalent in the Table API (ADR-0013), and M21 requires a stateful or custom operator in Java, so the ingestion job is DataStream. The serving job is Flink SQL: it projects the changelog onto rows and writes ClickHouse, and holds no keyed state, so SQL is the smaller artefact.

### 4.2 The Iceberg sink configuration

Format version **2**, in merge-on-read upsert mode, with `write.upsert.enabled=true` (or the per-statement `upsert-enabled`). Upsert and overwrite are mutually exclusive, and overwrite is batch-only. The equality fields are the declared primary key **union** every partition source column, because Iceberg fails the upsert precondition when a partition source column is missing from the key.

| Table | Primary key | Partition | Equality fields |
|---|---|---|---|
| `fact_order_line` | `(w_id, d_id, o_id, ol_number)` | `days(o_entry_d)` | `(w_id, d_id, o_id, ol_number, o_entry_d)` |
| `fact_delivery` | `(w_id, d_id, o_id)` | `days(o_entry_d)` | `(w_id, d_id, o_id, o_entry_d)` |
| `fact_stock` | `(s_w_id, s_i_id)` | none | `(s_w_id, s_i_id)` |

The partition transform is a baseline: M5 tests partition transforms on a hot table, and **a changed partition transform changes the equality fields**, so the two are decided together and the ADR records the link. The ClickHouse serving copy carries the same business key in its `ORDER BY` and is versioned by `source.lsn`.

### 4.3 The ordering operator

A custom Java keyed stateful operator sits between the Kafka source and the Iceberg sink. It keeps the maximum `source.lsn` seen per key and drops any record whose LSN is strictly less, so the sink's last-write-wins becomes highest-LSN-wins. Its state carries a time-to-live. A primary-key change is a DELETE, a tombstone and a CREATE on two keys: the null-value tombstone is dropped, and the other two are ordinary records. The full reasoning is in ADR-0013.

### 4.4 The Debezium and source configuration

- `table.exec.source.cdc-events-duplicate=true`: normalises the changelog and deduplicates a key's events within a commit. It complements the operator, which handles reordering, and does not replace it.
- Tombstones are dropped, because a null value carries no data.
- `provide.transaction.metadata` stays off. Ordering comes from the LSN; the only thing it would add is `transaction.total_order`, a per-transaction tie-break, and the trigger for revisiting it is a same-key, same-LSN collision that the operator cannot resolve.
- `snapshot.mode=initial` and the default `REPLICA IDENTITY`, because the upsert path only needs the key from the before image and the NULL-to-value test reads the after image.

## 5. The RIPE Atlas job

Flink SQL. Two outputs, both Iceberg format version 2 in upsert mode:

- **Raw results**, keyed by `result_id`, a hash over the stable measurement content only, partitioned `days(measurement_ts)` with equality fields `{result_id, measurement_ts}`. The REST backfill producer feeds the same topic, so a result delivered live and again by REST collapses to one row (ADR-0014).
- **A per-minute probe aggregate**: packets sent and received, loss rate, and average and maximum RTT, keyed by the window and the probe, so replay converges.

A **side output** carries two classes of record rather than letting them be averaged into a result: records that arrive past the watermark, and records whose `lts == -1`, which means the probe does not know whether its clock is in sync. Both feed the data-quality story M13 requires.

## 6. The watermark and lateness policy

Two sources, opposite policies, each with its reason.

**The CDC job assigns no watermark.** Its ordering token is the LSN, not event time, and it runs no event-time operator, so a watermark would be decoration. Debezium's `source.ts_ms` is carried as a column for partitioning and for the M8 freshness measurement, but it drives no window and drops no record.

**The RIPE job assigns a watermark over the probe timestamp**, with these bounds:

| Bound | Value | Reason |
|---|---|---|
| Bounded out-of-orderness | 2 minutes | Twice the window, and no finer than the one-second timestamp resolution allows; it bounds how long a window waits. |
| Window | 1 minute, tumbling, per probe | The granularity the probe aggregate needs, and the shortest window whose lateness can be reasoned against the publisher's reconnect gap. |
| Allowed lateness | 5 minutes | Matches the publisher's own `sendBacklog` window, described as the last few minutes, and the reconnect upload gap, so a result arriving after a brief disconnection is counted in its window rather than dropped. |
| Unsynchronised clock | `lts == -1` routed to the side output | The probe does not know its clock is in sync, so the record cannot be trusted for event time. |

All four are budgets, committed in `docs/budgets.yaml` before the late-event injection runs.

## 7. The state and checkpoint tuning plan

**Baseline.** RocksDB for the CDC ingestion job, because its keyed LSN state grows with distinct keys and RocksDB gives bounded heap and incremental checkpoints; HashMap for the serving and RIPE jobs, whose state is small or absent. Checkpoint interval 60 s, timeout 10 min, parallelism 2, Iceberg sink target file size 128 MB.

**The tuning record** changes at least three dimensions, each measured for throughput, checkpoint duration and end-to-end latency:

| Dimension | Values | Setting |
|---|---|---|
| Checkpoint interval | 10 s / 60 s / 180 s | `execution.checkpointing.interval` |
| Parallelism | 2 / 4 | `parallelism.default` |
| Sink flush size | 64 / 128 / 256 MB | the Iceberg sink's `write.target-file-size-bytes` |

The state backend is declared as the baseline rather than varied, because changing it changes the state representation and would confound the other two axes. If budget allows, a fourth arm compares HashMap with RocksDB for the ingestion job. The protocol is the evidence standard: fixed data volume, pinned versions, the exact command, raw output committed, and budgets declared before the measurement. Incident 2, the checkpoint timeout, has its permanent fix in Iceberg table properties rather than these knobs, so it does not duplicate this record.

## 8. Deduplication and idempotency

Both sources are ours to engineer, and the two mechanisms are different because the defects are different.

**The CDC path has three layers.** Flink's changelog deduplication collapses duplicates within a commit; the LSN operator drops strictly stale records, so the sink sees per-key LSN order; and the sink's checkpoint-id idempotency makes a replayed checkpoint a no-op. Together they cover in-commit duplication, reordering and replay. None of them covers source-transaction atomicity, which is not claimed (ADR-0002).

**The RIPE path has three.** The content-hash key collapses the live-and-backfilled overlap; the backfill producer is what makes a dropped result recoverable at all, since the live feed is at-most-once and never redelivers; and the window key makes the aggregate converge under replay. **Loss is not deduplication**: the feed drops results, and only the REST backfill recovers them, which is why the backfill is the correctness path rather than an optional extra.

## 9. Named constraints

1. Source-transaction atomicity is not claimed (ADR-0002).
2. No cross-domain join (ADR-0008).
3. Format version 2, not 3. The serving reader is the constraint, not Iceberg: ClickHouse 26.8 LTS cannot read v3 deletion vectors (support merged into 26.10.1.35; the next LTS is 27.3, March 2027), and the CDC facts are merge-on-read, so a v3 fact would break the read-through arm. The full-v3 question is owned by [the v3 stack review](https://github.com/SoongGuanLeong/de-platform/issues/22). Detail in `docs/data-contracts.md` section 6.1.
4. The per-key LSN claim is an inference from Postgres row-level locking, not a cited guarantee.
5. The RIPE content hash is ours to keep stable; changing its inputs changes the idempotency key.
6. Nothing here is measured.

## 10. Open measurements

- The tuning record's numbers, under the protocol in section 7.
- Whether the watermark bounds in section 6 hold up under the late-event injection; the bounds are budgets until then.
- The equality fields, which move if M5 revises the partition transform.
- Whether the ClickHouse connector's at-least-once behaviour under a mid-session failure matches the recovery the serving layer documents.

---

*Resolved by [the streaming-jobs ticket](https://github.com/SoongGuanLeong/de-platform/issues/13) on [the map](https://github.com/SoongGuanLeong/de-platform/issues/9). Inputs: [`docs/serving-layer.md`](serving-layer.md), [`docs/dataset-selection.md`](dataset-selection.md), [`docs/technology-selection.md`](technology-selection.md), [`docs/requirements-matrix.md`](requirements-matrix.md), [`docs/completion-bar.md`](completion-bar.md), [`docs/research/06-iceberg-flink-sink-write-modes.md`](research/06-iceberg-flink-sink-write-modes.md), [`docs/research/14-licence-and-cost-audit.md`](research/14-licence-and-cost-audit.md).*
