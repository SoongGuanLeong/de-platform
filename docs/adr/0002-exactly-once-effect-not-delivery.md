# Claim exactly-once effect on committed state, not exactly-once delivery

**Status:** accepted

The streaming path into Iceberg claims exactly-once effect on the committed table state, resting on the sink's checkpoint-id idempotency, and does not claim exactly-once delivery or describe the sink as performing upserts. Iceberg has no UPDATE: a change event is written as a new data file plus a key-only equality delete marking the prior row superseded, so calling the sink an upsert names a mechanism the storage layer does not have. That delete mechanism belongs to the Flink sink rather than to Iceberg: the Spark batch path writes position deletes instead, deletion vectors on format-version 3, and Spark has no equality-delete writer at all, so the two paths produce different delete-file evidence. Flink records source offsets at a checkpoint and rewinds on failure, so records after the last checkpoint are always reprocessed; the sink makes that harmless by stamping `flink.max-committed-checkpoint-id` into each snapshot and committing only strictly greater ids, which is idempotence at the commit rather than a transactional write.

## Considered options

- **Claim exactly-once delivery.** Rejected: false, because records after the last checkpoint are reprocessed on every failure.
- **Describe the sink as upserting into Iceberg.** Rejected: Iceberg has no UPDATE, so the claim is puncturable in a single interview question.
- **Claim source-transaction atomicity.** Rejected: Flink checkpoints do not align with PostgreSQL transaction boundaries.

## Consequences

Exactly-once holds for the table commit but not for end-to-end delivery, so upsert mode with declared equality fields is what absorbs duplicate delivery from Debezium; append mode does not. Correctness also depends, on the Flink path, on a bounded equality delete-file count that compaction collapses, which makes a compaction record part of the evidence. Matrix row M3.
