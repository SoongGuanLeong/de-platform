# Write CDC into Iceberg with Flink's native sink, not Kafka Connect

**Status:** accepted

Flink's native Iceberg sink in upsert mode, with declared equality fields on format version 2 or later, is the write path from Kafka into Iceberg. It is the only candidate that writes key-only equality deletes, so it is the only one whose committed state converges when Debezium redelivers a change, and it carries the checkpoint-id idempotency that ADR-0002 relies on. The Kafka Connect Iceberg sink is append-only, so a redelivered change becomes a duplicate row and the convergence claim fails.

## Considered options

- **Kafka Connect Iceberg sink.** Rejected: append-only. Two claims about it are false and worth recording, because the prior repository declared a Kafka Connect Iceberg sink that never existed. "Confluent's iceberg-kafka-connect" does not exist (the repository returns 404; Confluent's Iceberg product is Tableflow, a managed cloud feature), and the maintained-looking Databricks fork is explicitly not maintained, its code donated to Apache. The Apache `kafka-connect` module is active but append-only, per its own open issue #17542. The posting's "Kafka Connect" mention is satisfied by Debezium as a Kafka Connect source connector.
- **Spark Structured Streaming.** Rejected for the real-time path: append-only, needing `foreachBatch` plus `MERGE INTO`, which is batch work in a streaming wrapper.

## Consequences

The correctness claim is bounded: exactly-once effect on committed state, not delivery, and no source-transaction atomicity (ADR-0002). Upsert requires format v2 or later, declared equality fields, and every partition source column present among the equality fields. Sink configuration, the equality fields per table, and the format version belong to ticket [The streaming job designs](https://github.com/SoongGuanLeong/de-platform/issues/13). Evidence: ticket [The technology-selection matrix](https://github.com/SoongGuanLeong/de-platform/issues/8), research 06 and 10.
