# Enforce LSN order in a stateful operator, not by keying alone

**Status:** accepted

The CDC job keys the Kafka topic by the business primary key, so Kafka preserves LSN order per key within a partition. That is not enough for the convergence claim. The Iceberg upsert sink does not compare versions: on an insert or update it writes a key-only equality delete plus the new row, so the last committed write wins regardless of which event carried the higher LSN. A reordered stale event arriving after a fresh one would delete the fresh row and reinstate the superseded one, and M2's convergence test feeds a deliberately shuffled and duplicated stream. The job therefore runs a custom Java keyed stateful operator between the Kafka source and the Iceberg sink. It keeps the maximum `source.lsn` seen per key and drops any record whose LSN is strictly less, so the stream reaching the sink is LSN-monotonic per key and the sink's last-write-wins coincides with highest-LSN-wins. The operator is the stateful Java component M21 requires.

The ordering claim is per key, not global. `source.lsn` is a per-row WAL position and is not monotonic in commit order across overlapping transactions, and Debezium exposes no per-transaction commit LSN (open request `debezium/dbz#2353`). Postgres serialises writes to a row, so the LSN of successive changes to one key is monotonic, and that is the property the operator relies on. This is an inference from row-level locking, recorded as reasoning rather than as a cited fact.

A primary-key change is not an update. Debezium emits a DELETE for the old key, a tombstone (a null value) for the old key, then a CREATE for the new key. The tombstone carries no data and is dropped in the job; the DELETE and the CREATE are handled by the operator and the sink as ordinary records on two different keys, so the old row is removed and the new one written. The operator's keyed state carries a time-to-live, so a key that stops changing releases its state rather than growing the checkpoint without bound.

## Considered options

- **Kafka keying alone.** Rejected: it preserves per-key order within a partition but not across a partition-count change, and it does not make the sink version-aware, so it fails the shuffled-stream test as written.
- **Flink SQL deduplication** with `ROW_NUMBER() OVER (PARTITION BY key ORDER BY lsn DESC)` over a window. Rejected: state is bounded by the window, but a record is only emitted when the window closes, which adds latency to every row.
- **Enable Debezium transaction metadata and order by `transaction.total_order`.** Rejected: it is per-transaction only, so it does not order across transactions, and the commit LSN the design would prefer is not exposed.

## Consequences

The CDC ingestion job is a DataStream job rather than a Flink SQL job, because the operator has no keyed-state equivalent in the Table API. Its keyed state is part of the checkpoint, so the state backend and checkpoint behaviour are load-bearing and are fixed by the tuning plan. `table.exec.source.cdc-events-duplicate=true` is enabled as well: it normalises the changelog and deduplicates a key's events within a commit, which is a different problem from reordering and complements the operator rather than replacing it. Format version 2, because the sink's key-only equality-delete path is what the operator feeds. Matrix rows M2 and M3.
