# 10 - Iceberg write path for a Debezium CDC upsert pipeline: Flink vs Kafka Connect vs Spark Structured Streaming

**Date of research:** 2026-09-28. All evidence accessed 2026-09-28 unless stated.
**Scope:** which write path a Debezium CDC -> Kafka -> Iceberg pipeline should use when it must apply upserts, given that the platform already runs Flink (streaming) and Spark (batch), and that ADR-0002 claims exactly-once EFFECT on committed state via checkpoint-id idempotency with the Flink sink in upsert mode.
**Question answered:** for a CDC pipeline that must apply upserts, which of (a) the Apache Iceberg Flink sink, (b) the Kafka Connect Iceberg sink, or (c) the Spark Structured Streaming Iceberg sink should be the write path, and which should be rejected on merit.
**Exact version read:** Apache Iceberg **1.11.0**, git tag `apache-iceberg-1.11.0`, published **2026-05-20** [S1]. Where the Kafka Connect module is concerned I also read the **`main` branch as of 2026-09-28**, because the module has changed since 1.11.0 [S29]. Flink facts are read from `flink/v2.0` and the 1.11.0 docs; Spark facts from `spark/v4.0` and the 1.11.0 docs.

This document deliberately re-verifies the Flink claims rather than only citing research 06 [S25], and it tests the Kafka Connect claim that the prior Olist repo made and never implemented (a Kafka Connect Iceberg sink that applies upserts) against the actual source [S26].

---

## 1. Method, and the bar the write path has to clear

Every claim below is traced to a primary source: the Apache Iceberg source tree at a pinned tag, the project's own documentation at that tag, the project's issue/PR tracker, a package registry, or the project's own release metadata. No secondary blog decides anything. Where a documentation claim contradicts the code, I say so and prefer the code.

The bar is **ADR-0002** [S27], which claims exactly-once EFFECT on committed table state, resting on the sink's checkpoint-id idempotency, and explicitly rejects describing the sink as upserting. It states the mechanism precisely:

- Iceberg has no UPDATE. A change event is written as a new data file plus a key-only equality delete marking the prior row superseded.
- The equality-delete mechanism belongs to the Flink sink. The Spark path writes position deletes instead (deletion vectors on format-version 3) and has no equality-delete writer, so the two paths leave different delete-file evidence.
- Flink records source offsets at a checkpoint and rewinds on failure, so records after the last checkpoint are always reprocessed; the sink makes that harmless by stamping `flink.max-committed-checkpoint-id` into each snapshot and committing only strictly greater ids. That is idempotence at the commit, not a transactional write.

So the test for each candidate is: **does it write key-based deletes (equality deletes) so that the table converges under duplicate delivery, and does it have a commit-level idempotency guard?** A path that only appends fails the ADR-0002 claim for a CDC upsert pipeline, because Flink's own Debezium documentation states Debezium is at-least-once on failover [S28], and an append-only sink turns a redelivered change into a duplicate row.

---

## 2. The three candidates at a glance

| | (a) Flink native Iceberg sink | (b) Kafka Connect Iceberg sink | (c) Spark Structured Streaming Iceberg sink |
|---|---|---|---|
| Upsert / CDC support | **Yes**, native upsert mode and an equality-delete CDC path [S22] | **No**. Append-only at 1.11.0 and on `main`; upsert/CDC keys are not present [S3], [S10], [S11], [S29] | **No** native. `append` and `complete` only; upsert needs `foreachBatch` + `MERGE INTO` (batch) [S17], [S21] |
| Delete mechanism | Key-only equality deletes (upsert) or full-row equality deletes (CDC path) [S22], [S25] | none. Writes data files only [S4], [S6], [S12] | Position deletes / deletion vectors via merge-on-read row-level operations; **no equality-delete writer** [S19], [S20], [S27] |
| Commit-level idempotency | Yes: `flink.max-committed-checkpoint-id` in the snapshot summary [S24], [S25] | Yes, but by Kafka offsets: `kafka.connect.offsets.*` in the snapshot summary plus a snapshot-ancestry validator [S7] | Yes: `spark.sql.streaming.queryId` + `spark.sql.streaming.epochId` in the snapshot summary [S18] |
| Exactly-once scope | Commit only; end-to-end needs a replayable source and durable checkpoint [S22], [S25] | Commit only; docs claim "exactly-once delivery" but the guarantee is the append commit [S2] | Commit only; Spark checkpoint + epoch-id guard [S18] |
| Commit trigger | Flink checkpoint completion (`notifyCheckpointComplete`), one atomic Iceberg commit per checkpoint in the CDC/upsert path [S25] | A coordinator elected from the control-topic consumer group, on a commit interval (default 300,000 ms) or when all tasks report ready [S7] | Spark micro-batch epoch, one Iceberg commit per epoch [S18] |
| Project / release | Apache Iceberg 1.11.0, ASF governance, released 2026-05-20 [S1] | Apache Iceberg 1.11.0 module, ASF governance, but append-only [S2], [S3]; the pre-donation Databricks/Tabular distribution is unmaintained [S13] | Apache Iceberg 1.11.0, ASF governance [S1] |
| Runs locally | Yes, in the Flink cluster the platform already runs | Yes, but adds a Connect worker, a control topic and a coordinator election | Yes, but adds a continuously running Spark session |
| JD requirement demonstrated | "real-time upserts / streaming"; "real-time streaming jobs in Flink, including partitioning, compaction, and job/state tuning" | "Kafka Connect ... write into it" (the only JD basis; but see the Confluent finding in Section 4) | "Apache Spark (batch silver/gold), both reading and writing Iceberg" |

---

## 3. (a) The Flink native Iceberg sink

### 3.1 What it guarantees

The sink is the only candidate with a real upsert path. Upsert requires three things, all enforced or documented at 1.11.0 [S22]:

1. Iceberg **format v2** (or v3). "Iceberg supports `UPSERT` based on the primary key when writing data into v2 table format."
2. **Equality fields declared**, either as a SQL `PRIMARY KEY(...) NOT ENFORCED` or as Iceberg identifier fields.
3. The mode enabled, either by table property `write.upsert.enabled=true` or by the write option `upsert-enabled=true`.

For a partitioned table, every partition field's source column must be in the equality fields, otherwise the sink fails its build precondition [S22]. That is the guard that stops an update in partition A from failing to delete the old row in partition B.

The Iceberg docs state flatly: "The Flink Iceberg sink guarantees exactly-once semantics." [S22]. Read with the code, that guarantee is exactly-once **for the Iceberg commit**. Files for a checkpoint are staged at checkpoint time and committed at most once, guarded by the snapshot summary property `flink.max-committed-checkpoint-id`, alongside `flink.job-id` and `flink.operator-id` [S24], [S25]. On restore the committer recomputes the committed id from the table and commits only the strict tail, so replaying an already-committed checkpoint is a no-op [S25]. The same docs note commits can fail while checkpoints succeed, so the table can lag the checkpoint; it does not duplicate or partially apply [S22].

The distinction that matters for CDC is not the checkpoint guarantee (identical across modes) but **idempotency under source-level redelivery**. Upsert mode makes the table converge: an update is written as a key-only equality delete plus a full-row data record in the same `RowDelta`, and an equality delete applies only to data files whose data sequence number is strictly less than the delete's [S25]. So a later delete-key removes an earlier row, and a redelivered change cannot leave two live rows for one key.

### 3.2 Commit and checkpoint model

Checkpoint-driven two-phase, Flink's protocol rather than a cross-system XA [S25]:

1. At checkpoint time each writer flushes data and delete files to temporary locations and emits a committable keyed by checkpoint id; the state is snapshotted so it survives restart.
2. After the checkpoint completes, a single committer commits the staged files as one atomic Iceberg snapshot.

In the CDC/upsert case the committer commits **one `RowDelta` per checkpoint**, deliberately not merging checkpoints, because the equality deletes of a later transaction must apply to the data files of the earlier one [S25]. Iceberg's contribution to idempotency is not an XA transaction; it is the snapshot summary metadata [S24], [S25]. A crash after the checkpoint but before the commit is repaired on restore, which commits the pending tail [S25].

### 3.3 Operational footprint and maturity

Runs inside the Flink cluster the platform already operates for the real-time path; no third engine and no extra commit coordinator. The one maintenance obligation the docs call out is that snapshot expiration and orphan-file cleanup must keep the last Flink snapshot and only delete orphans old enough, otherwise the job's recovery state can be corrupted [S22]. Compaction of equality delete files is part of the evidence, as ADR-0002 notes.

Maturity: Apache Iceberg, ASF governance, released 1.11.0 on 2026-05-20 [S1]. The sink has two implementations: the legacy `FlinkSink` (SQL default, because `table.exec.iceberg.use-v2-sink` defaults to `false`) and the opt-in SinkV2 `IcebergSink` [S23]. Both share the write modes and the checkpoint-id idempotency; the SQL flag is the only difference in configuration surface [S25].

### 3.4 Verdict on (a)

This is the write path that satisfies ADR-0002 exactly as written: equality deletes in upsert mode, checkpoint-id idempotency, one atomic commit per checkpoint. It also demonstrates the JD's most specific streaming requirement ("real-time upserts / streaming", "real-time streaming jobs in Flink"). It is not merely adequate; it is the only candidate that does the job.

---

## 4. (b) The Kafka Connect Iceberg sink

### 4.1 First, a naming correction that the assignment itself needs

The assignment asks about "Confluent's iceberg-kafka-connect distribution". That distribution does not exist as an open-source project:

- `https://github.com/confluentinc/iceberg-kafka-connect` returns **404** [S15].
- A GitHub repository search for `org:confluentinc iceberg` returns **0** results [S15].
- Confluent's Iceberg offering is **Tableflow**, which Confluent's own docs describe as "a Confluent Cloud feature that materializes Apache Kafka topics as Apache Iceberg or Delta Lake tables" [S16]. Tableflow is a managed cloud feature, not a Kafka Connect sink connector, and it cannot run locally.

The real lineage of the open-source connector is Tabular -> Databricks -> Apache Iceberg:

- `https://github.com/tabular-io/iceberg-kafka-connect` redirects (HTTP 301) to `https://github.com/databricks/iceberg-kafka-connect` [S14].
- The `databricks/iceberg-kafka-connect` README opens with: "THIS REPOSITORY IS NOT MAINTAINED AS THE CODE HAS BEEN DONATED TO THE UPSTREAM APACHE ICEBERG PROJECT", and points to the Apache Iceberg `kafka-connect` module [S13].
- That repo's last release is **v0.6.19, 2024-06-06**, and its last commit is **2025-07-03**, a README edit [S13].

A second third-party option, `getindata/kafka-connect-iceberg-sink`, is **archived** (last push 2025-04-23) [S30]. It fails the observable-activity floor outright.

So there are only two things that could be called "the Kafka Connect Iceberg sink" in 2026: the unmaintained Databricks/Tabular distribution (fails the longevity floor: not maintained, no release in over two years), and the Apache Iceberg module (ASF governance, active). The platform should consider only the Apache one, and the rest of this section is about it.

### 4.2 The Apache Iceberg Kafka Connect module is real, released, and active

It is not vapourware. At tag 1.11.0 the repo has a top-level `kafka-connect` directory with four sub-modules: `kafka-connect`, `kafka-connect-events`, `kafka-connect-runtime`, `kafka-connect-transforms` [S3]. `iceberg-kafka-connect` is published to Maven Central at 1.11.0 [S31], and the runtime distribution is built by the Iceberg Gradle build [S2]. The module has commits through 2026-09-25, including Kafka Connect-specific fixes on 2026-09-17 and 2026-09-08 [S26]. On longevity it passes: ASF foundation governance, observable activity.

### 4.3 But it is append-only, and does not support upsert or CDC

This is the load-bearing finding, and it is stated by the project's own maintainers and contributors, not inferred from a blog.

**Source evidence (1.11.0).** The writer path writes data files only:

- `RecordUtils.createTableWriter` builds either an `UnpartitionedWriter` or the module's own `PartitionedAppendWriter` [S4].
- `PartitionedAppendWriter` extends `PartitionedFanoutWriter`, a plain append writer, and writes no delete files [S6].
- `IcebergWriter.write` writes every non-null record and ignores only tombstones ("ignore tombstones...") [S5]. There is no row-kind handling, no op-code handling, and no call to any equality-delete writer.
- The only mention of equality fields is that `RecordUtils` sets `equalityFieldIds` and `equalityDeleteRowSchema` on the `GenericFileWriterFactory` when identifier fields exist [S4]. Those settings are consumed only by delta writers (`BaseDeltaTaskWriter` subclasses); the writers actually used here never call the equality-delete writer, so no delete files are produced. It is vestigial wiring, not a working upsert path.

**Tracker evidence.** The project says the same thing directly:

- Issue **#17542** (opened 2026-08-06, still open), titled "Kafka Connect: real CDC upsert/delete support (equality-deletes) - restoring and fixing pre-donation cdc-field/upsert functionality", states: "Neither made it into the code donated to `apache/iceberg` - the current `kafka-connect` module is append-only." [S10].
- Issue **#15046** (opened 2026-01-14, open) reports the user experience: "I am using `io.tabular.iceberg.connect.IcebergSinkConnector` to test upsert and it is running well. But use apache version there is no update and lots of duplicates even if enabled upsert-mode." [S11].
- PR **#15499**, "Enable Upsert and Delete Support in Apache Iceberg Kafka Connect", was **closed unmerged on 2026-04-10**. Its description: "The current implementation of Apache Iceberg Kafka Connect supports append-only writes and does not provide native support for upsert or delete operations. Out-of-the-box, the following writers are used: `UnpartitionedWriter<T>`, `PartitionedFanoutWriter<T>`. These writers support only append-based writes, meaning: No row-level updates, No delete handling, No delta file generation." [S12].
- Issue **#10842** "Kafka Connect: Add delta writer support" (open since 2024-08-01) and PR **#12070** (open since 2025-01-23) are the in-flight, unreleased work to add delta writers [S10], [S12].
- Issue **#17455** (open, 2026-07-31) reports "duplicate PK rows when two PK updates land in one snapshot after a crash", which is the expected outcome of an append-only sink with no key dedup [S10].

**Config evidence.** The 1.11.0 configuration reference lists `iceberg.tables.default-id-columns` but has **no** `cdc-field` and **no** `upsert-mode-enabled`, the two properties the pre-donation distribution documented [S2]. The Apache module's `IcebergSinkConfig.java` at 1.11.0 has no upsert or CDC constant at all, and the `main` branch as of 2026-09-28 is the same [S3], [S29]. So the old keys are silently ignored as unknown connector properties.

**Documentation defect to flag.** The same 1.11.0 doc still claims, in its feature list, "Exactly-once delivery semantics" [S2], and it still documents a "CDC feature" via the `DebeziumTransform` and `DmsTransform` SMTs that add `_cdc.op`, `_cdc.ts`, `_cdc.source`, `_cdc.key` fields [S2]. But the sink module contains no reference to those fields and no code that acts on `_cdc.op`. The transform produces metadata columns; the sink writes them as ordinary columns. This is a documentation claim about a capability the sink does not implement, and it is exactly the kind of plausible-sounding claim the assignment warned about.

### 4.4 What its "exactly-once" actually is

The connector does have a genuine commit-coordination protocol, and it is worth describing accurately because it is the closest thing to an equivalent of the Flink mechanism:

- A **control topic** (default `control-iceberg`) carries the coordination events. One task is elected coordinator (it holds the first control-topic partition) [S7].
- The coordinator sends `StartCommit`; workers write files and reply `DataWritten` then `DataComplete`; when all partitions are ready (or the commit times out) the coordinator commits to Iceberg [S7].
- The Iceberg commit is an `AppendFiles` when there are no delete files, or a `RowDelta` when there are [S7]. Since the writers never produce delete files (Section 4.3), in practice it is always `AppendFiles`.
- The snapshot summary records `kafka.connect.offsets.<topic>.<group>`, `kafka.connect.commit-id`, `kafka.connect.task-id` and `kafka.connect.valid-through-ts`. A `SnapshotAncestryValidator` compares the offsets it is about to commit against the offsets recorded in the latest snapshot and rejects a stale commit [S7].
- The control-topic producer is transactional: `beginTransaction` -> send events -> `sendOffsetsToTransaction` -> `commitTransaction`, which is the KIP-447 mechanism the docs cite [S8], [S2].

So the Kafka Connect sink has commit-level idempotency **by Kafka offsets**, not by Flink checkpoint id. That is a real, source-backed mechanism. But it is exactly-once for an **append** commit. It has no upsert mode and no equality deletes, so it cannot make the table converge under Debezium's at-least-once redelivery [S28]. Its "exactly-once delivery semantics" is about not re-appending the same Kafka offsets, not about one live row per key.

### 4.5 Verdict on (b)

Rejected as the write path for the CDC upsert pipeline. It is ASF-governed and locally runnable, but it cannot apply upserts at 1.11.0 or on `main` today, and its docs claim a capability it does not have. The unmaintained Databricks/Tabular distribution and the archived getindata connector are worse. Kafka Connect remains necessary in the stack for its real job: **Debezium runs as a Kafka Connect source connector** [S30], and the JD's "Kafka Connect" mention is satisfied by that ingestion role, not by an Iceberg sink.

---

## 5. (c) Spark Structured Streaming's Iceberg sink

### 5.1 What it guarantees

The native streaming sink supports exactly two output modes, documented at 1.11.0 [S17]:

- `append`: appends the rows of every micro-batch.
- `complete`: replaces the table contents every micro-batch.

There is no `update` mode, no upsert mode, and no row-level delete. Continuous processing is explicitly unsupported because it "doesn't provide the interface to commit the output" [S17].

The commit-level idempotency is genuinely analogous to Flink's, and it is in the source [S18]. `SparkWrite.BaseStreamingWrite.commit(long epochId, ...)`:

- records `spark.sql.streaming.queryId` and `spark.sql.streaming.epochId` in the snapshot summary;
- reads the last committed epoch for this query id from the snapshot history and, if `epochId <= lastCommittedEpochId`, logs "Skipping epoch ... as it was already committed" and returns without committing.

So a replayed Spark micro-batch is a no-op at the commit, exactly as a replayed Flink checkpoint is. `StreamingAppend` commits an `AppendFiles`; `StreamingOverwrite` commits a `ReplacePartitions` [S18].

### 5.2 Upserts require dropping out of the sink

To apply CDC upserts with Spark you cannot use the streaming sink's modes. The standard pattern is `foreachBatch` plus a Spark SQL `MERGE INTO` (which requires the Iceberg Spark extensions) [S21]. That is a batch row-level operation per micro-batch, not a streaming sink mode. Its properties differ from the Flink sink in the way ADR-0002 already records:

- Iceberg Spark row-level operations default to **copy-on-write**: `write.delete.mode`, `write.update.mode` and `write.merge.mode` all default to `copy-on-write` [S19]. A `MERGE INTO` "rewrite[s] only the affected data files" [S21].
- The alternative is `merge-on-read`, which writes **position deletes** (and deletion vectors on format-version 3) via `SparkPositionDeltaWrite`, which uses `PositionDeltaWriter`, `ClusteredPositionDeleteWriter` and `FanoutPositionOnlyDeleteWriter` and a `RowDelta` [S20].
- Spark has **no equality-delete writer**. The Spark module's delete classes are all position-based; the equality-delete classes that appear in the tree are read-side metrics and readers, not writers [S20]. This confirms the ADR-0002 statement.

So a Spark `foreachBatch` + `MERGE INTO` upsert leaves different delete-file evidence from the Flink sink (position deletes or full file rewrites, versus key-only equality deletes), and it does not use the streaming sink's epoch-id commit guard; its exactly-once effect rests on `MERGE INTO` being naturally idempotent for a replayed deterministic batch, which is a weaker and different argument.

### 5.3 Operational footprint and maturity

Spark Structured Streaming requires a continuously running Spark session (driver plus executors) for the real-time path. On a 12 CPU / 7-8 GB host that is a large second JVM footprint alongside Flink, Kafka, Connect, Polaris and ClickHouse. The JD assigns Spark to "batch silver/gold", not to real-time CDC; running Spark Streaming for the same CDC stream duplicates Flink's role. Maturity is the same Apache Iceberg 1.11.0 release [S1].

### 5.4 Verdict on (c)

Rejected for the real-time upsert path, retained for batch silver/gold. Its native streaming sink is append/complete only and cannot upsert; the `foreachBatch` + `MERGE INTO` workaround abandons the epoch-id commit guard and produces position-delete or copy-on-write evidence, not equality deletes. It is not wrong in general, but it is the wrong tool when Flink is already in the stack and the requirement is real-time upserts.

---

## 6. ADR-0002 test: does Kafka Connect offer an equivalent?

**No.** ADR-0002's claim is exactly-once effect on committed state, with the Flink sink in upsert mode, resting on checkpoint-id idempotency. The Kafka Connect path fails on the load-bearing clause:

| ADR-0002 requirement | Flink sink | Kafka Connect sink |
|---|---|---|
| Writes key-based (equality) deletes so the table converges under redelivery | Yes, upsert mode writes a key-only equality delete plus the new row in one `RowDelta` [S22], [S25] | No. Append-only; no delete files are produced [S4], [S6], [S10], [S12] |
| Commit-level idempotency guard | Yes: `flink.max-committed-checkpoint-id` in the snapshot summary [S24], [S25] | Yes, but by Kafka offsets: `kafka.connect.offsets.*` plus a snapshot-ancestry validator [S7]. Not checkpoint id, and not a substitute for key dedup |
| Absorbs duplicate delivery from Debezium | Yes, in upsert mode; append mode does not [S25], [S28] | No. A redelivered change becomes a duplicate row [S10], [S11] |

The Kafka Connect sink's offset-in-snapshot idempotency prevents **its own** replay from re-appending the same offsets. It does nothing about a logical change that Debezium redelivers as a new Kafka record, because there is no key and no delete. The two mechanisms are not equivalent for the purpose ADR-0002 states. **Adopting the Kafka Connect sink as the write path would break ADR-0002**, and the prior Olist repo's declaration of an Iceberg Kafka Connect sink that applied upserts is exactly the unsupported claim this section disproves.

---

## 7. Recommendation

**Use the Flink native Iceberg sink in upsert mode as the write path for the Debezium CDC -> Kafka -> Iceberg upsert pipeline.** Both implementations work; the SQL default is the legacy `FlinkSink` (`table.exec.iceberg.use-v2-sink=false`) and the opt-in SinkV2 `IcebergSink` is the forward-looking one [S23], [S25]. The table must be format v2 (or v3) with a declared primary key or identifier fields, and upsert enabled via `write.upsert.enabled=true` or `upsert-enabled=true` [S22]. For a partitioned table, include the partition source columns in the equality fields [S22]. Keep the last Flink snapshot and only delete old orphan files in maintenance [S22], and compact the equality delete files as part of the pipeline.

Rationale: it is the only candidate that writes equality deletes, so it is the only one whose committed state converges under Debezium's at-least-once redelivery; it has the checkpoint-id idempotency ADR-0002 describes; and it uses the Flink engine the platform already runs, so it adds no engine and no second commit coordinator.

**Rejected: the Kafka Connect Iceberg sink as the write path.** The Apache Iceberg module is ASF-governed and active, but it is append-only at 1.11.0 and on `main`; the pre-donation Databricks/Tabular distribution is explicitly unmaintained and its upsert keys are silently ignored; and "Confluent's iceberg-kafka-connect" does not exist (Confluent's offering is the managed, cloud-only Tableflow). It cannot apply upserts and would break ADR-0002. Keep Kafka Connect only as the Debezium source runtime, which is what the JD's "Kafka Connect" mention actually requires.

**Rejected for the real-time path: Spark Structured Streaming's Iceberg sink.** Its native sink is append/complete only; upserts require a batch `foreachBatch` + `MERGE INTO` that produces position deletes or copy-on-write rewrites, not equality deletes, and abandons the epoch-id commit guard. Spark stays where the JD puts it: batch silver/gold.

**On "is it genuinely necessary":** the Kafka Connect Iceberg sink is not necessary and should not be built. Kafka Connect is necessary, but as the Debezium source, not as an Iceberg writer. Adding a third Iceberg write engine on a 7-8 GB host is footprint without a capability the Flink sink lacks.

---

## 8. What I could not verify, and known discrepancies

- **Documentation defect (verified):** the Apache Iceberg 1.11.0 Kafka Connect docs claim "Exactly-once delivery semantics" and describe a CDC feature via `DebeziumTransform`/`DmsTransform` and `_cdc.*` fields, while the sink module is append-only and contains no code that acts on `_cdc.op` [S2], [S3], [S5]. Treat the CDC feature description as aspirational, not shipped.
- **Unreleased work in flight:** delta writer support (issue #10842, PR #12070) and real CDC upsert/delete support (issue #17542) are open, unreleased [S10], [S12]. They would change this verdict if and when they ship; they cannot be relied on today.
- **Not measured:** I did not run any of the three paths, so I state no throughput, latency or row-count numbers. The performance and footprint statements are structural (which engines must run, what files are written), not benchmarked.
- **Not read in full:** the Flink SinkV2 `Committer` invocation timing (FLIP-191) is covered in research 06 [S25] as an open item and does not change the comparison here. The Debezium at-least-once statement is taken from Flink's Debezium format documentation via research 06 [S28]; I did not independently read Debezium's own exactly-once documentation.
- **Confluent naming:** I could not find any Confluent-published open-source Kafka Connect Iceberg sink. The 404 and the zero-result org search are the evidence; if the assignment intended a private or renamed Confluent distribution, it is not publicly verifiable [S15].

---

## Sources

All accessed 2026-09-28 unless stated. "tag 1.11.0" means `apache-iceberg-1.11.0`.

| ID | Source | URL | Date |
|---|---|---|---|
| S1 | Apache Iceberg release list, tag `apache-iceberg-1.11.0` published 2026-05-20 | https://api.github.com/repos/apache/iceberg/releases | 2026-05-20 |
| S2 | Iceberg docs, "Kafka Connect" (`docs/docs/kafka-connect.md`), tag 1.11.0: feature list incl. "Exactly-once delivery semantics"; config table (no cdc-field / upsert-mode-enabled); KIP-447 requirement; CDC transform section with `_cdc.*` | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/docs/docs/kafka-connect.md | 2026-09-28 |
| S3 | `kafka-connect/IcebergSinkConfig.java`, tag 1.11.0: only `id-columns`; no upsert or CDC constant | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/kafka-connect/kafka-connect/src/main/java/org/apache/iceberg/connect/IcebergSinkConfig.java | 2026-09-28 |
| S4 | `kafka-connect/data/RecordUtils.java`, tag 1.11.0: `createTableWriter` selects `UnpartitionedWriter` / `PartitionedAppendWriter`; sets `equalityFieldIds` on the factory (unused by append writers) | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/kafka-connect/kafka-connect/src/main/java/org/apache/iceberg/connect/data/RecordUtils.java | 2026-09-28 |
| S5 | `kafka-connect/data/IcebergWriter.java`, tag 1.11.0: writes every non-null record, "ignore tombstones...", no row-kind handling | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/kafka-connect/kafka-connect/src/main/java/org/apache/iceberg/connect/data/IcebergWriter.java | 2026-09-28 |
| S6 | `kafka-connect/data/PartitionedAppendWriter.java`, tag 1.11.0: extends `PartitionedFanoutWriter` (append only) | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/kafka-connect/kafka-connect/src/main/java/org/apache/iceberg/connect/data/PartitionedAppendWriter.java | 2026-09-28 |
| S7 | `kafka-connect/channel/Coordinator.java`, tag 1.11.0: `AppendFiles` vs `RowDelta`; `kafka.connect.offsets/commit-id/task-id/valid-through-ts`; `SnapshotAncestryValidator`; coordinator election and commit interval | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/kafka-connect/kafka-connect/src/main/java/org/apache/iceberg/connect/channel/Coordinator.java | 2026-09-28 |
| S8 | `kafka-connect/channel/Channel.java`, tag 1.11.0: transactional producer `beginTransaction` / `sendOffsetsToTransaction` / `commitTransaction` | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/kafka-connect/kafka-connect/src/main/java/org/apache/iceberg/connect/channel/Channel.java | 2026-09-28 |
| S9 | `kafka-connect/channel/CommitterImpl.java` and `IcebergSinkTask.java`, tag 1.11.0: worker/coordinator split; `preCommit` returns empty (offsets handled by the worker) | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/kafka-connect/kafka-connect/src/main/java/org/apache/iceberg/connect/IcebergSinkTask.java | 2026-09-28 |
| S10 | Apache Iceberg issue #17542, "Kafka Connect: real CDC upsert/delete support (equality-deletes) - restoring and fixing pre-donation cdc-field/upsert functionality", open, opened 2026-08-06: "the current `kafka-connect` module is append-only"; also issue #10842, #17455 | https://github.com/apache/iceberg/issues/17542 | 2026-08-06 |
| S11 | Apache Iceberg issue #15046, "Does kafka connector it support upsert", open, opened 2026-01-14: apache version "no update and lots of duplicates even if enabled upsert-mode" | https://github.com/apache/iceberg/issues/15046 | 2026-01-14 |
| S12 | Apache Iceberg PR #15499, "Enable Upsert and Delete Support in Apache Iceberg Kafka Connect", closed unmerged 2026-04-10: current implementation "supports append-only writes"; `UnpartitionedWriter` / `PartitionedFanoutWriter`; also PR #12070 | https://github.com/apache/iceberg/pull/15499 | 2026-04-10 |
| S13 | `databricks/iceberg-kafka-connect` README (not maintained; donated to Apache Iceberg) and repo metadata (last release v0.6.19 2024-06-06; last commit 2025-07-03) | https://github.com/databricks/iceberg-kafka-connect | 2025-07-03 |
| S14 | `tabular-io/iceberg-kafka-connect` HTTP 301 redirect to `databricks/iceberg-kafka-connect` | https://github.com/tabular-io/iceberg-kafka-connect | 2026-09-28 |
| S15 | `confluentinc/iceberg-kafka-connect` returns HTTP 404; GitHub repo search `org:confluentinc iceberg` returns 0 results | https://api.github.com/repos/confluentinc/iceberg-kafka-connect | 2026-09-28 |
| S16 | Confluent docs, "Tableflow in Confluent Cloud": managed feature that materializes Kafka topics as Iceberg or Delta tables | https://docs.confluent.io/cloud/current/topics/tableflow/overview.html | 2026-09-28 |
| S17 | Iceberg docs, "Spark Structured Streaming" (`docs/docs/spark-structured-streaming.md`), tag 1.11.0: `append` and `complete` output modes only; no continuous processing; commit-rate guidance | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/docs/docs/spark-structured-streaming.md | 2026-09-28 |
| S18 | `spark/v4.0/.../source/SparkWrite.java`, tag 1.11.0: `BaseStreamingWrite` epoch-id idempotency (`spark.sql.streaming.queryId`, `spark.sql.streaming.epochId`); `StreamingAppend` / `StreamingOverwrite` | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/spark/v4.0/spark/src/main/java/org/apache/iceberg/spark/source/SparkWrite.java | 2026-09-28 |
| S19 | Iceberg docs, "Configuration" (`docs/docs/configuration.md`), tag 1.11.0: `write.delete.mode`, `write.update.mode`, `write.merge.mode` default `copy-on-write` | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/docs/docs/configuration.md | 2026-09-28 |
| S20 | `spark/v4.0/.../source/SparkPositionDeltaWrite.java`, tag 1.11.0: position deletes and `RowDelta`; no equality-delete writer in the Spark module | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/spark/v4.0/spark/src/main/java/org/apache/iceberg/spark/source/SparkPositionDeltaWrite.java | 2026-09-28 |
| S21 | Iceberg docs, "Spark Writes" (`docs/docs/spark-writes.md`), tag 1.11.0: `MERGE INTO` rewrites affected data files; row-level delete requires Iceberg Spark extensions | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/docs/docs/spark-writes.md | 2026-09-28 |
| S22 | Iceberg docs, "Flink Writes" (`docs/docs/flink-writes.md`), tag 1.11.0: "The Flink Iceberg sink guarantees exactly-once semantics"; UPSERT requires v2 + PK + `write.upsert.enabled`/`upsert-enabled`; partitioned equality-field rule; commit-failure metrics; snapshot/orphan maintenance warning | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/docs/docs/flink-writes.md | 2026-09-28 |
| S23 | `flink/v2.0/.../FlinkConfigOptions.java`, tag 1.11.0: `table.exec.iceberg.use-v2-sink` `defaultValue(false)` | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.0/flink/src/main/java/org/apache/iceberg/flink/FlinkConfigOptions.java | 2026-09-28 |
| S24 | `flink/v2.0/.../sink/SinkUtil.java`, tag 1.11.0: `flink.job-id`, `flink.operator-id`, `flink.max-committed-checkpoint-id`; `getMaxCommittedCheckpointId` | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.0/flink/src/main/java/org/apache/iceberg/flink/sink/SinkUtil.java | 2026-09-28 |
| S25 | Internal prior art: `docs/research/06-iceberg-flink-sink-write-modes.md` (2026-09-27), Flink sink write modes, upsert/equality-delete mechanics, checkpoint-driven commit, exactly-once scope | repo file | 2026-09-27 |
| S26 | Apache Iceberg `kafka-connect` commit history: Kafka Connect fixes 2026-09-17 and 2026-09-08; last repo commit touching the module path 2026-09-25 | https://api.github.com/repos/apache/iceberg/commits?path=kafka-connect | 2026-09-28 |
| S27 | Internal ADR: `docs/adr/0002-exactly-once-effect-not-delivery.md` (accepted), exactly-once effect on committed state via checkpoint-id idempotency with the Flink sink in upsert mode | repo file | 2026-09-27 |
| S28 | Flink Debezium format docs (`debezium.md`), cited via research 06 [S23]: Debezium is at-least-once on failover; `PRIMARY KEY` + `table.exec.source.cdc-events-duplicate` recommendation | https://github.com/apache/flink/blob/master/docs/content/docs/connectors/table/formats/debezium.md | 2026-09-28 |
| S29 | `kafka-connect/IcebergSinkConfig.java` on `main` as of 2026-09-28: still only `id-columns`, no upsert/CDC constant | https://github.com/apache/iceberg/blob/main/kafka-connect/kafka-connect/src/main/java/org/apache/iceberg/connect/IcebergSinkConfig.java | 2026-09-28 |
| S30 | `getindata/kafka-connect-iceberg-sink` archived (last push 2025-04-23); Debezium connectors are Kafka Connect source connectors (JD stack: "Ingestion / streaming: Debezium CDC -> Apache Kafka") | https://github.com/getindata/kafka-connect-iceberg-sink | 2026-09-28 |
| S31 | Maven Central: `org.apache.iceberg:iceberg-kafka-connect` versions, latest 1.11.0 | https://search.maven.org/solrsearch/select?q=g:org.apache.iceberg+AND+a:iceberg-kafka-connect | 2026-09-28 |

---

## Verdict

**The write path for a Debezium CDC -> Kafka -> Iceberg upsert pipeline is the Flink native Iceberg sink in upsert mode.** It is the only one of the three candidates that writes key-only equality deletes, so it is the only one whose committed state converges under duplicate delivery; it has the checkpoint-id idempotency ADR-0002 rests on; and it uses the Flink engine already in the stack. The Kafka Connect Iceberg sink is rejected: the Apache module is append-only at 1.11.0 and on `main` (its own maintainers say so, and the pre-donation upsert keys are silently ignored), the Databricks/Tabular distribution is unmaintained, and "Confluent's iceberg-kafka-connect" does not exist. Spark Structured Streaming is rejected for the real-time path: its native sink is append/complete only, and the `foreachBatch` + `MERGE INTO` workaround writes position deletes or copy-on-write rewrites rather than equality deletes. **Confidence: high** for the Flink and Kafka Connect verdicts, where I read the source and the project's own tracker at a pinned tag; **high** for the Spark verdict on the sink modes and delete mechanisms, **medium** on the exact foreachBatch retry semantics, which rest on `MERGE INTO` idempotency rather than a source-read guard.
