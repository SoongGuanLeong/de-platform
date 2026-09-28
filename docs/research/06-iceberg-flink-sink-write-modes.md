# 06 - Iceberg Flink sink write modes and exactly-once effect on final table state

**Date of research:** 2026-09-27. All evidence accessed 2026-09-27 unless stated.
**Scope:** Apache Iceberg's Flink connector (DataStream sink and Table API / SQL sink), specifically the write modes, distribution modes, failure and restart behaviour, CDC / upsert equality-delete path, and commit protocol.
**Question answered:** Which write modes does the Iceberg Flink sink expose, and which of them actually give exactly-once effect on the final Iceberg table state?

**Exact version read:** Apache Iceberg **1.11.0**, git tag `apache-iceberg-1.11.0`, published **2026-05-20** ([S1]). Where behaviour differs by module I say so; the repo ships separate Flink modules for **Flink 1.20, 2.0 and 2.1** (directories `flink/v1.20`, `flink/v2.0`, `flink/v2.1` under tag 1.11.0, [S2]). I read the `flink/v2.0` source as the reference copy; I spot-checked that the same sink classes exist under `flink/v1.20` and `flink/v2.1` (file listing, [S2]). Version support mapping to a specific Flink release is an inference from the directory layout, not a documented statement I found.

---

## 1. Method and what "exactly-once" is being measured against

Every claim below is traced to one of three kinds of primary source:

1. the Iceberg docs tree at tag 1.11.0 (the Markdown that generates iceberg.apache.org/docs/latest),
2. the Iceberg Java source at tag 1.11.0,
3. the Iceberg release notes / merged PR titles at tag 1.11.0 and 1.10.0.

I distinguish (i) what the documentation states, (ii) what the source code does, and (iii) what I infer. Where the two disagree I say so.

"Exactly-once on final table state" is used strictly as: **for every record that the source delivers to the sink, the final committed Iceberg table reflects it exactly once**. It is deliberately narrower than "exactly-once for the streaming job end to end", which additionally requires a replayable source and a durable Flink checkpoint. Section 5 makes that split explicit.

---

## 2. There are two sink implementations, and SQL picks between them

| Implementation | Class | API | Default? |
|---|---|---|---|
| Legacy sink | `org.apache.iceberg.flink.sink.FlinkSink` | DataStream builder + Table API | **Yes, for SQL and DataStream** |
| SinkV2 sink | `org.apache.iceberg.flink.sink.IcebergSink` | DataStream builder (`Sink<RowData>`) + Table API | Opt-in |
| Dynamic sink | `org.apache.iceberg.flink.sink.dynamic.DynamicIcebergSink` | DataStream only, multi-table routing | Opt-in |

**SQL default is the legacy sink.** `FlinkConfigOptions.TABLE_EXEC_ICEBERG_USE_V2_SINK` (`table.exec.iceberg.use-v2-sink`) has `defaultValue(false)` [S3]. `IcebergTableSink.getSinkRuntimeProvider` reads that flag and calls `createIcebergSink` only when true, otherwise `createLegacySink` [S4]. The docs confirm: "To turn on SinkV2 based implementation in SQL, set `SET table.exec.iceberg.use-v2-sink = true;`" [S5].

Both sinks share the same commit idea and the same helper for the resume point, `SinkUtil.getMaxCommittedCheckpointId` [S6], but the mechanics differ (Section 7). This matters for the answer: **the write modes and the exactly-once guarantee are the same for both, but the class you configure and the SQL flag you need are not.**

---

## 3. (a) Write modes and distribution modes, named exactly as the code names them

### 3.1 DataStream sink (the `IcebergSink` builder, and the legacy `FlinkSink` builder)

There is **no single "write mode" enum**. The mode is the combination of two independent booleans on the builder, plus the presence of equality fields:

| Mode | How it is named in code | Default | Source |
|---|---|---|---|
| Append | neither `overwrite(true)` nor `upsert(true)` | yes | [S7] |
| Overwrite | `Builder#overwrite(boolean)` | `false` | [S7], [S8] |
| Upsert | `Builder#upsert(boolean)` | `false` | [S7], [S8] |
| Equality-delete CDC (non-upsert) | `Builder#equalityFieldColumns(List<String>)` with upsert left off | `null` | [S7], [S9] |
| Branch write | `Builder#toBranch(String)` | main | [S10] |

- `overwrite` and `upsert` are **mutually exclusive**: `IcebergSink.build()` asserts `!overwriteMode` when upsert is on [S7].
- Upsert requires non-empty equality fields: `IcebergSink.build()` asserts `!equalityFieldIds.isEmpty()` [S7].
- `equalityFieldColumns` on its own (without upsert) is the "CDC" path that writes equality deletes for `UPDATE_BEFORE` / `DELETE` row kinds. See Section 6.

The DataStream builder also exposes these write options via `Builder#set(String,String)` / `setAll(Map)`; the keys are defined in `FlinkWriteOptions` [S8]:

`write-format`, `target-file-size-bytes`, `compression-codec`, `compression-level`, `compression-strategy`, **`upsert-enabled`**, **`overwrite-enabled`**, **`distribution-mode`**, `range-distribution-statistics-type`, `range-distribution-sort-key-base-weight`, `branch`, `write-parallelism`, `compaction-enabled` (deprecated), `rewrite-data-files.enabled`, `expire-snapshots.enabled`, `delete-orphan-files.enabled`, `table-refresh-interval`, `uid-suffix`.

Note the DataStream keys are **unprefixed** (`upsert-enabled`), whereas the table property is prefixed (`write.upsert.enabled`). The SQL layer presents the same unprefixed keys as write options.

### 3.2 Table API / SQL sink

The SQL surface is the same modes, reached by SQL verb or hint [S5], [S11]:

| Mode | SQL surface | Notes |
|---|---|---|
| Append | `INSERT INTO ... SELECT` | streaming allowed |
| Overwrite | `INSERT OVERWRITE ...` / `INSERT OVERWRITE t PARTITION(...) ...` | **batch only**; code asserts `!overwrite \|\| context.isBounded()` [S4], docs say streaming does not support it [S5] |
| Upsert | `CREATE TABLE ... PRIMARY KEY(...) NOT ENFORCED` plus either table property `write.upsert.enabled=true` or write option `upsert-enabled=true` (hint `/*+ OPTIONS('upsert-enabled'='true') */`) | v2 format required [S5], [S12] |

SQL write options (the same set as the DataStream `set` keys) are documented in the Flink configuration page [S11]; the load-bearing ones are `upsert-enabled` (overrides table `write.upsert.enabled`), `overwrite-enabled` (default `false`), and `distribution-mode` (overrides table `write.distribution-mode`).

The SQL sink derives the equality columns from the **resolved schema's primary key**: `IcebergTableSink.getSinkRuntimeProvider` builds `equalityColumns` from `physicalColumnsOnlySchema.getPrimaryKey()` (or the legacy `TableSchema` primary key) and passes it to `equalityFieldColumns` [S4]. So in SQL, declaring the primary key on the table is not cosmetic: it is the mechanism by which the sink learns the equality fields.

### 3.3 Distribution modes

`DistributionMode` is an enum in the Iceberg API module with exactly three values [S13]:

`NONE` ("none"), `HASH` ("hash"), `RANGE` ("range").

- DataStream: `Builder#distributionMode(DistributionMode)` accepts all three; the Javadoc on `IcebergSink.Builder#distributionMode` says "Currently, flink support NONE and HASH and RANGE" [S7]. Range has two extra knobs: `rangeDistributionStatisticsType(StatisticsType)` with values `Auto` (default), `Map`, `Sketch`, and `rangeDistributionSortKeyBaseWeight(double)` default `0.0` [S7], [S8].
- SQL: write option `distribution-mode` (or table property `write.distribution-mode`), string values `none` / `hash` / `range` [S11], [S14].
- **Default is `none`.** `FlinkWriteConf.distributionMode()` falls back to `TableProperties.WRITE_DISTRIBUTION_MODE_NONE` after checking the write option then the table property [S15]. `write.distribution-mode` has no default in `TableProperties`; the sink's own default is `none` [S14], [S15].
- `NONE` does not mean "no shuffle at all" when equality fields are set: `IcebergSink.distributeDataStreamByNoneDistributionMode` still does `input.keyBy(new EqualityFieldKeySelector(...))` if `equalityFieldIds` is non-empty, so that all rows for a key reach one writer [S16].
- `RANGE` with equality fields set does **not** range-distribute: the code logs a warning and falls back to `keyBy` on the equality fields, because "Range distribution for primary keys are not always safe in Flink streaming writer" [S16].

**Documentation defect worth flagging.** The 1.11.0 docs page `flink-writes.md` still carries the warning: "The `RANGE` distribution mode is not yet available for the `IcebergSink`" [S5]. The 1.11.0 code contradicts it: `IcebergSink.distributeDataStream` has a `case RANGE` branch calling `distributeDataStreamByRangeDistributionMode` [S16], and the 1.10.0 release notes contain "Flink: port range distribution to v2 iceberg sink" (PR #12071) and its backports [S17]. **The code is right and the warning is stale.** The legacy `FlinkSink` Javadoc is stale in the same way ("support NONE and HASH") while its code also has a `case RANGE` [S18].

The **Dynamic sink** is narrower: the docs table for `DynamicRecord` says its `DistributionMode` is "NONE, HASH or `null`. When `null`, the record won't be shuffled at all" [S5]. No RANGE.

---

## 4. (b) Failure and restart semantics

All modes share **one commit protocol**, so the coarse answer is the same for all of them. The precise mechanism is in Section 7; this section states the observable behaviour.

**Records written after the last completed checkpoint but before the failure.** They are never committed to the table. The writers flush data and delete files at each checkpoint into temporary files and hand a committable (a manifest of those files, keyed by checkpoint id) to the committer; the table snapshot is only written when the commit for that checkpoint runs [S19], [S20]. So a crash before that commit leaves those files uncommitted (orphaned on storage until cleanup). On restart the source rewinds to the last completed checkpoint and re-delivers those records, and the sink writes and commits them again.

**Does replay produce duplicate rows in the table?** For a normal Flink restart from checkpoint state, **no**, for every mode. Two mechanisms enforce this:

1. Each commit records the checkpoint id it corresponds to in the snapshot summary as `flink.max-committed-checkpoint-id`, alongside `flink.job-id` and `flink.operator-id` [S6], [S20]. On restore the committer reads that value back and only commits checkpoints strictly greater than it [S6], [S21], [S22]. Replaying an already-committed checkpoint is therefore a no-op.
2. The source replays only from the restored checkpoint, so records already committed at or before it are not re-sent.

**The one documented way to break this** is losing the sink's own operator state, for example by changing the operator uid and restarting with `--allowNonRestoredState`. The `IcebergSink.Builder#uidSuffix` Javadoc states it directly: "`--allowNonRestoredState` can lead to data loss if the Iceberg commit failed in the last completed checkpoint" [S7]. That is data loss, not duplication, because the writer's temp-file list is gone.

**Per-mode nuances:**

| Mode | Replay after Flink restart | Upstream duplicate delivery (source redelivers the same logical record) |
|---|---|---|
| Append | exactly-once on table state | **duplicates are committed as extra rows.** There is no key and no delete, so nothing dedupes them. Relevant because Flink's own Debezium docs state Debezium is at-least-once on failover [S23]. |
| Overwrite | batch only, and `ReplacePartitions` is atomic [S5], [S20] | batch semantics; not a streaming replay case |
| Equality-delete CDC (upsert off, equality fields set) | exactly-once | duplicates within a checkpoint collapse (position deletes, Section 6); duplicates across commits are removed by the later equality delete |
| Upsert | exactly-once | idempotent by key: the later delete-key (higher sequence number) removes the earlier row, and same-checkpoint repeats are collapsed in the writer |

**Inference, labelled:** the difference between append and upsert is not the sink's checkpoint guarantee (identical for both) but **idempotency under source-level redelivery**. For a Debezium -> Kafka -> Flink CDC pipeline, append mode is only exactly-once if the source is, and Flink's docs say Debezium is at-least-once on failover [S23]; upsert mode is what makes the table converge regardless.

---

## 5. (c) Documented exactly-once versus at-least-once

**What the documentation states.** The Flink writes page opens with a flat claim: "The Flink Iceberg sink guarantees exactly-once semantics." [S5]. I found **no mode documented as at-least-once** anywhere in `flink-writes.md`, `flink-configuration.md`, `flink-ddl.md` or `flink.md` at 1.11.0 [S5], [S11], [S12], [S24].

**What that sentence actually covers.** Reading the code, the guarantee is exactly-once **for the Iceberg commit**:

- Files for a checkpoint are committed at most once (the `max-committed-checkpoint-id` guard) and every checkpoint up to the last committed one is committed exactly once (the committer commits the whole pending tail, not just the latest checkpoint) [S20], [S21], [S22].
- The commit itself is atomic and serializable (Section 7), so a reader never sees a half-applied checkpoint.

**What it does not cover, stated by the docs themselves.** The same page's metrics section spells out the gap between a successful checkpoint and a successful commit [S5]:

- "Iceberg commit happened after successful Flink checkpoint in the `notifyCheckpointComplete` callback. It could happen that Iceberg commits failed (for whatever reason), while Flink checkpoints succeeding."
- "It could also happen that `notifyCheckpointComplete` wasn't triggered (for whatever bug). As a result, there won't be any Iceberg commits attempted."

So the table can **lag** the checkpoint. It does not get duplicate or partial data from this; the pending commits are retried at the next checkpoint or on restore (Section 7). The docs recommend alerting on `elapsedSecondsSinceLastSuccessfulCommit` [S5].

**Exactly-once for the streaming job end to end** is a stronger property that the sink alone cannot provide. It additionally needs (i) Flink checkpointing enabled with a durable, restorable state backend, (ii) a source that can replay from the checkpoint (e.g. Kafka offsets held in Flink state), and (iii) restoring the job from that checkpoint with a stable operator uid. The sink's contribution is that it is a checkpoint-driven transactional sink; the end-to-end property is Flink's 2PC contract plus the source.

**Bottom line for (c):** every mode is documented and implemented as exactly-once for the table commit. The modes are not where the at-least-once risk lives; the risk lives in source replay semantics and in losing sink state.

---

## 6. (d) Equality deletes for CDC / upsert input

### 6.1 What is required to enable upsert

Three things, all enforced or documented:

1. **Iceberg format v2** (or v3). The docs: "Iceberg supports `UPSERT` based on the primary key when writing data into v2 table format" [S5].
2. **Equality fields declared.** In SQL, `PRIMARY KEY(...) NOT ENFORCED` in the DDL (or Iceberg identifier fields); `flink-ddl.md` says the primary key "is required for UPSERT mode" [S12]. In DataStream, `Builder#equalityFieldColumns(List<String>)`. `SinkUtil.checkAndGetEqualityFieldIds` falls back to the table's `identifierFieldIds()` when no columns are passed, and warns if the passed columns differ from the identifier fields [S6].
3. **Enable the mode**: table property `write.upsert.enabled=true` (default `false` [S14]), or the write option `upsert-enabled=true` which overrides the table property [S5], [S8], [S15].

For a **partitioned** table, every partition field's source column must be in the equality fields, otherwise `IcebergSink.build()` fails the precondition [S7]; the docs state the same [S5]. This is what stops an update in partition A from failing to delete the old row in partition B.

### 6.2 The Flink source side

The sink needs a changelog that contains `UPDATE_BEFORE` / `UPDATE_AFTER` / `DELETE` row kinds. Flink's Debezium JSON format produces those from Debezium events [S23]. The Flink Debezium docs recommend declaring a `PRIMARY KEY` on the source table and enabling `table.exec.source.cdc-events-duplicate` so Flink normalises and deduplicates the changelog [S23]. In SQL the Iceberg sink reads the primary key off the resolved schema to get its equality columns [S4], so a Kafka `debezium-json` source table declared with `PRIMARY KEY(...) NOT ENFORCED` is the standard way to feed upsert mode.

**Correction, 2026-09-28 (ticket #15).** This platform does **not** use `debezium-json` on the wire. The CDC topics carry Avro, with the producer as Debezium's Kafka Connect `AvroConverter` in `as-confluent` mode and the reader as Flink's `avro-confluent` format, against Apicurio's ccompat v7 endpoint. The reason is the compatibility gate: completion bar 6.1 requires a backward-incompatible schema to be rejected by the serializer, which only a registry-backed serializer can do. The Iceberg-side requirements in this section are unchanged; only the source-table format changes, from `debezium-json` to `avro-confluent`. Recorded in ADR-0020 and `docs/data-contracts.md` section 4.

**Inference, labelled:** the Iceberg docs do not contain a Kafka/Debezium upsert example at 1.11.0 (I searched `flink.md`, `flink-writes.md`, `flink-connector.md`, `flink-ddl.md`); the Kafka-side requirement is documented by Flink, not by Iceberg. The Iceberg-side requirement (v2 format, equality fields, upsert flag) is documented by Iceberg.

### 6.3 How updates are represented on disk

The writer chosen depends on equality fields and upsert:

- No equality fields -> plain `UnpartitionedWriter` or `RowDataPartitionedFanoutWriter` (data files only) [S25].
- Equality fields present -> `UnpartitionedDeltaWriter` or `PartitionedDeltaWriter`, which extend `BaseDeltaTaskWriter` and write **both** data files and equality-delete files [S25], [S26].

The row-kind handling in `BaseDeltaTaskWriter.write` is the key table [S26]:

| Row kind | upsert = true | upsert = false (CDC / equality fields) |
|---|---|---|
| `INSERT`, `UPDATE_AFTER` | `deleteKey(key)` then `write(row)` | `write(row)` |
| `UPDATE_BEFORE` | ignored (break) | `delete(row)` |
| `DELETE` | `deleteKey(key)` | `delete(row)` |

What the two delete variants put in the file [S25], [S26], [S27]:

- `deleteKey` writes **only the equality field columns** into the equality-delete file. `RowDataTaskWriterFactory` sets `equalityDeleteRowSchema(TypeUtil.select(schema, equalityFieldIds))` in upsert mode, and `BaseDeltaTaskWriter` projects the key with `keyProjection` before writing [S25], [S26]. `deleteKey` -> `eqDeleteWriter.write(key)`.
- `delete` writes the **whole row** into the equality-delete file. In non-upsert mode `RowDataTaskWriterFactory` sets `equalityDeleteRowSchema(schema)` (full schema) [S25], and `BaseDeltaTaskWriter` passes the full row [S26].

So in upsert mode an update is represented on disk as **one equality-delete record containing the key columns, plus one data record containing the full new row**, committed in the same `RowDelta` transaction. A delete is a key-only equality-delete record.

**Same-key repeats within one commit are collapsed with a position delete, not an equality delete.** `BaseTaskWriter.BaseEqualityDeltaWriter.write` keeps an `insertedRowMap` keyed by the equality fields; when the same key is written again in the same writer it emits a **position delete** pointing at the previous data row's path and row offset, so only the latest row survives [S27]. `deleteKey` does the same: if the key was inserted in this writer it position-deletes the inserted row instead of writing an equality delete [S27]. This is why the docs' keyBy-based distribution modes matter for upsert: all rows for a key must land in one writer for this collapse to work, which `keyBy(EqualityFieldKeySelector)` guarantees [S16].

**Format v3 note.** `RowDataTaskWriterFactory.initialize` sets `useDv = TableUtil.formatVersion(table) > 2` and passes it to the delta writers, which use a `PartitioningDVWriter` for deletion vectors instead of position-delete files [S25]. Equality deletes still behave as described.

**Read-side semantics that make this correct.** Per the Iceberg spec, an equality delete file applies to a data file only when "the data file's data sequence number is *strictly less than* the delete's data sequence number" [S28]. That is exactly why a same-commit insert is not erased by its own key delete, and why a later commit's delete-key removes an earlier commit's row.

---

## 7. (e) Commit frequency, atomicity, and the two-phase story

### 7.1 Is it once per checkpoint?

The commit is **checkpoint-driven**, with one deliberate exception for empty checkpoints.

**Legacy sink (`IcebergFilesCommitter`, used by SQL by default).** The commit happens in `notifyCheckpointComplete(long checkpointId)`. It commits all pending checkpoints up to and including that id, guarded by `checkpointId > maxCommittedCheckpointId`, then advances `maxCommittedCheckpointId` [S21]. The class comment explains the out-of-order case: if `notifyCheckpointComplete(ckpId+1)` arrives before `notifyCheckpointComplete(ckpId)`, the later call for the smaller id is skipped because everything was already committed [S21]. If a checkpoint has no files, the commit is skipped, but every `flink.max-continuous-empty-commits` consecutive empty checkpoints (default **10**, from `IcebergCommitter.MAX_CONTINUOUS_EMPTY_COMMITS` / the same property in the legacy committer) an empty snapshot is committed so the recorded checkpoint id keeps advancing [S20], [S21].

**SinkV2 (`IcebergCommitter`, opt-in).** The SinkV2 framework hands the committer the committables staged by the writers, and the Iceberg implementation is written to be correct whether it is called once per checkpoint or with a batch; it returns early on an empty collection [S29], [S20]. It groups requests by checkpoint id into a `TreeMap`, reads the already-committed id from the table, calls `signalAlreadyCommitted` on everything at or below it, and commits the strict tail [S20]. There is exactly **one committer subtask**: `IcebergSink.addPreCommitTopology` forces `.global().setParallelism(1).setMaxParallelism(1)` on the write aggregator and committer, with the comment "This is to ensure commit only happen in one committer subtask" [S16].

**One commit per checkpoint, or more?** For append-only checkpoints (no delete files) the committer merges all pending checkpoints into a single `AppendFiles` commit [S20]. When delete files are present it commits **each checkpoint separately** as its own `RowDelta`, deliberately not merging, with the code comment: "We don't commit the merged result into a single transaction because for the sequential transaction txn1 and txn2, the equality-delete files of txn2 are required to be applied to data files from txn1. Committing the merged one will lead to the incorrect delete semantic." [S20]. So: **one atomic commit per checkpoint in the CDC/upsert case; possibly one merged commit covering several checkpoints in the append case.**

### 7.2 Is the commit atomic with respect to concurrent readers?

**Yes.** The commit is an Iceberg snapshot commit, and Iceberg's own reliability page states: "Commits replace the path of the current table metadata file using an atomic operation. This ensures that all updates to table data and metadata are atomic, and is the basis for serializable isolation." and "the writer attempts to commit by atomically swapping the new table metadata file for the existing metadata file. If the atomic swap fails because another writer has committed, the failed writer retries by writing a new metadata tree based on the new current table state." [S30]. A reader sees either the pre-commit or post-commit snapshot, never a partial checkpoint. `INSERT OVERWRITE` uses the same atomic mechanism via `ReplacePartitions`, which the docs call out as atomic [S5], [S20].

### 7.3 Is there a documented two-phase-commit / commit-coordinator story?

**There is a two-phase protocol, and it is Flink's, not a cross-system XA.** The phases are:

1. **Phase 1, at checkpoint time:** each writer flushes its data and delete files to temporary locations and emits a `WriteResult` / committable keyed by checkpoint id; the state is snapshotted so it survives a restart [S16], [S19], [S20].
2. **Phase 2, after the checkpoint completes:** the single committer commits the staged files to the Iceberg table as one atomic snapshot [S20], [S21].

Iceberg's contribution to idempotency is not an XA transaction; it is the **snapshot summary metadata**. Every commit sets `flink.max-committed-checkpoint-id`, `flink.job-id` and `flink.operator-id` on the snapshot [S20], [S21]. On restore, `SinkUtil.getMaxCommittedCheckpointId` walks the snapshot history (following parent snapshots, matching the job id and operator id) to recover the resume point [S6]. This is how a replayed or retried commit is made a no-op.

The `IcebergCommitter` class Javadoc states the assumptions it relies on: one `IcebergCommittable` per checkpoint, no late checkpoints, and no other writer producing a commit on the same branch with the same jobId-operatorId-checkpointId triplet [S20].

### 7.4 What happens if the job fails after the checkpoint completes but before the commit?

The pending data is **committed on restore, not lost and not duplicated**:

- **Legacy sink:** `IcebergFilesCommitter.initializeState` restores `dataFilesPerCheckpoint` from operator state, recomputes `maxCommittedCheckpointId` from the table snapshot summary using the old job id, takes the tail of checkpoints greater than it, and calls `commitUpToCheckpoint(...)` immediately if that tail is non-empty [S22]. So a crash between checkpoint completion and commit is repaired at recovery.
- **SinkV2:** the restored committables are handed back to `IcebergCommitter.commit`; it recomputes the committed id from the table and commits the tail [S20].

The only failure mode the docs flag as losing data is losing the sink operator state itself (`--allowNonRestoredState` with a changed operator uid) [S7].

### 7.5 Operational hazard the docs call out

Because the sink depends on the **last snapshot's summary** and on **temporary uncommitted files**, the docs warn: "expiring snapshots and deleting orphan files could possibly corrupt the state of the Flink job. To avoid that, make sure to keep the last snapshot created by the Flink job (which can be identified by the `flink.job-id` property in the summary), and only delete orphan files that are old enough." [S5]. This is a direct consequence of the commit protocol above and is worth an explicit guard in any maintenance job.

---

## 8. What I could not verify, and known discrepancies

- **Stale doc warning (verified discrepancy):** `flink-writes.md` says RANGE is unavailable for `IcebergSink`; the code implements it and the 1.10.0 release notes record the port [S5], [S16], [S17].
- **Stale Javadoc (verified discrepancy):** `FlinkSink.Builder#distributionMode` Javadoc says only NONE and HASH; the code has a RANGE branch [S18].
- **No Kafka example in Iceberg docs (verified absence):** the Debezium / Kafka source-side requirement is documented by Flink [S23], not by Iceberg at 1.11.0.
- **UNVERIFIED:** I did not find a primary statement that the SinkV2 `Committer#commit` is called on every checkpoint completion rather than only when committables exist; the Iceberg code is written to be correct under either invocation pattern (it is idempotent and handles an empty collection by returning early [S20]). I looked at the Flink `Committer` interface Javadoc [S29], which describes the contract but does not spell out the invocation timing; the authoritative statement is Flink's SinkV2 design (FLIP-191), which I did not read in full. This does not change the answer because the Iceberg committer's idempotency does not depend on it.
- **UNVERIFIED:** exact per-version Flink support matrix (1.20 / 2.0 / 2.1) is inferred from module directories, not from a release note I read end to end.

---

## Sources

All accessed 2026-09-27. "tag 1.11.0" means `apache-iceberg-1.11.0`.

- **S1.** Iceberg release list (GitHub REST API), tag `apache-iceberg-1.11.0`, published 2026-05-20T08:47:57Z. https://api.github.com/repos/apache/iceberg/releases
- **S2.** Iceberg repository directory listing at tag 1.11.0, `flink/` -> `v1.20`, `v2.0`, `v2.1`; `flink/v2.0/flink/src/main/java/org/apache/iceberg/flink/sink/` file list. https://github.com/apache/iceberg/tree/apache-iceberg-1.11.0/flink
- **S3.** `FlinkConfigOptions.java`, tag 1.11.0, `TABLE_EXEC_ICEBERG_USE_V2_SINK` = `table.exec.iceberg.use-v2-sink`, `defaultValue(false)`. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.0/flink/src/main/java/org/apache/iceberg/flink/FlinkConfigOptions.java
- **S4.** `IcebergTableSink.java`, tag 1.11.0 (sink runtime provider, `overwrite \|\| isBounded` check, primary-key to equality-columns, legacy vs V2 selection). https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.0/flink/src/main/java/org/apache/iceberg/flink/IcebergTableSink.java
- **S5.** Iceberg docs, "Flink Writes" (`docs/docs/flink-writes.md`), tag 1.11.0: exactly-once claim, INSERT INTO / INSERT OVERWRITE / UPSERT, `write.upsert.enabled` and `upsert-enabled`, OVERWRITE-UPSERT exclusivity, distribution modes, SinkV2 warning about RANGE, `table.exec.iceberg.use-v2-sink`, metrics and commit-failure notes, snapshot/orphan maintenance warning. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/docs/docs/flink-writes.md
- **S6.** `SinkUtil.java`, tag 1.11.0: `checkAndGetEqualityFieldIds`, `getMaxCommittedCheckpointId`, constants `flink.job-id`, `flink.operator-id`, `flink.max-committed-checkpoint-id`. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.0/flink/src/main/java/org/apache/iceberg/flink/sink/SinkUtil.java
- **S7.** `IcebergSink.java`, tag 1.11.0: builder methods `overwrite`, `upsert`, `equalityFieldColumns`, `distributionMode`, `rangeDistributionStatisticsType`, `rangeDistributionSortKeyBaseWeight`, `uidSuffix`; `build()` upsert validations; `addPreCommitTopology` single-committer wiring. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.0/flink/src/main/java/org/apache/iceberg/flink/sink/IcebergSink.java
- **S8.** `FlinkWriteOptions.java`, tag 1.11.0: DataStream write option keys and defaults. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.0/flink/src/main/java/org/apache/iceberg/flink/FlinkWriteOptions.java
- **S9.** `IcebergSinkBuilder.java`, tag 1.11.0: `equalityFieldColumns`, `overwrite`, `upsert`, `distributionMode` interface. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.0/flink/src/main/java/org/apache/iceberg/flink/sink/IcebergSinkBuilder.java
- **S10.** `IcebergSink.java` branch handling and `toBranch`; docs "Branch Writes" [S5]. (Same file as S7.)
- **S11.** Iceberg docs, "Flink Configuration" (`docs/docs/flink-configuration.md`), tag 1.11.0, Write options table. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/docs/docs/flink-configuration.md
- **S12.** Iceberg docs, "Flink DDL" (`docs/docs/flink-ddl.md`), tag 1.11.0, `PRIMARY KEY` section: required for UPSERT mode. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/docs/docs/flink-ddl.md
- **S13.** `DistributionMode.java`, tag 1.11.0: `NONE` / `HASH` / `RANGE` and `modeName()`. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/api/src/main/java/org/apache/iceberg/DistributionMode.java
- **S14.** `TableProperties.java`, tag 1.11.0: `write.distribution-mode` values, `write.upsert.enabled`, `UPSERT_ENABLED_DEFAULT = false`. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/core/src/main/java/org/apache/iceberg/TableProperties.java
- **S15.** `FlinkWriteConf.java`, tag 1.11.0: `distributionMode()` default `none`; `upsertMode()` default false. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.0/flink/src/main/java/org/apache/iceberg/flink/FlinkWriteConf.java
- **S16.** `IcebergSink.java`, tag 1.11.0, distribution and topology methods: `distributeDataStream` `case NONE/HASH/RANGE`, `distributeDataStreamByNoneDistributionMode` keyBy equality fields, RANGE-with-equality-fields fallback warning, `addPreCommitTopology` global/parallelism-1. (Same file as S7.)
- **S17.** Iceberg release notes, `apache-iceberg-1.10.0`: "Flink: port range distribution to v2 iceberg sink" (PR #12071) and "Flink: Backport IcerbegSink RANGE distribution to Flink 1.19 and 2.0" (PR #13228); also "Docs, Flink: Fix equality fields requirement in upsert mode" (PR #13127) and "Docs: Add EOS note to Flink docs" (PR #13875). https://github.com/apache/iceberg/releases/tag/apache-iceberg-1.10.0
- **S18.** `FlinkSink.java`, tag 1.11.0: `Builder#distributionMode` Javadoc and the `case RANGE` branch in `build()`. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.0/flink/src/main/java/org/apache/iceberg/flink/sink/FlinkSink.java
- **S19.** `IcebergStreamWriter.java` / `IcebergSinkWriter.java`, tag 1.11.0: writer flushes files and emits `WriteResult` at checkpoint. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.0/flink/src/main/java/org/apache/iceberg/flink/sink/IcebergSinkWriter.java
- **S20.** `IcebergCommitter.java`, tag 1.11.0: class Javadoc assumptions, `commit()` grouping and `signalAlreadyCommitted`, `commitDeltaTxn` single-Append vs per-checkpoint `RowDelta` with the equality-delete ordering comment, `MAX_CONTINUOUS_EMPTY_COMMITS` default 10, `commitOperation` setting the snapshot summary properties. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.0/flink/src/main/java/org/apache/iceberg/flink/sink/IcebergCommitter.java
- **S21.** `IcebergFilesCommitter.java`, tag 1.11.0: `MAX_COMMITTED_CHECKPOINT_ID` comment, `notifyCheckpointComplete` out-of-order handling, empty-commit skip, `commitUpToCheckpoint`. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.0/flink/src/main/java/org/apache/iceberg/flink/sink/IcebergFilesCommitter.java
- **S22.** `IcebergFilesCommitter.java`, tag 1.11.0, `initializeState`: restore `dataFilesPerCheckpoint`, recompute `maxCommittedCheckpointId` from the table, commit the uncommitted tail from the old job. (Same file as S21.)
- **S23.** Flink docs source, Debezium format (`docs/content/docs/connectors/table/formats/debezium.md`), branch master: UPDATE_BEFORE/UPDATE_AFTER encoding, at-least-once caveat and `PRIMARY KEY` + `table.exec.source.cdc-events-duplicate` recommendation, PostgreSQL REPLICA IDENTITY FULL requirement. https://github.com/apache/flink/blob/master/docs/content/docs/connectors/table/formats/debezium.md
- **S24.** Iceberg docs, "Flink" (`docs/docs/flink.md`), tag 1.11.0: no CDC/Debezium example. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/docs/docs/flink.md
- **S25.** `RowDataTaskWriterFactory.java`, tag 1.11.0: equality-delete schema selection (key-only in upsert, full row otherwise), `useDv = formatVersion > 2`, writer selection. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.0/flink/src/main/java/org/apache/iceberg/flink/sink/RowDataTaskWriterFactory.java
- **S26.** `BaseDeltaTaskWriter.java`, tag 1.11.0: row-kind to delete/write mapping, `deleteKey` vs `delete`, `DeleteGranularity.FILE`. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.0/flink/src/main/java/org/apache/iceberg/flink/sink/BaseDeltaTaskWriter.java
- **S27.** `BaseTaskWriter.java`, tag 1.11.0, inner class `BaseEqualityDeltaWriter`: `insertedRowMap` keyed by equality fields, same-writer same-key collapse via position delete, `deleteKey`. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/core/src/main/java/org/apache/iceberg/io/BaseTaskWriter.java
- **S28.** Iceberg table spec (`format/spec.md`), tag 1.11.0, Scan Planning: "An equality delete file must be applied to a data file when ... The data file's data sequence number is strictly less than the delete's data sequence number". https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/format/spec.md
- **S29.** Flink `Committer.java` interface Javadoc, branch master. https://github.com/apache/flink/blob/master/flink-core/src/main/java/org/apache/flink/api/connector/sink2/Committer.java
- **S30.** Iceberg docs, "Reliability" (`docs/docs/reliability.md`), tag 1.11.0: atomic metadata replacement, serializable isolation, optimistic retry on conflict. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/docs/docs/reliability.md

---

## Verdict

**The sink has three real write modes - append, overwrite, upsert - plus an unnamed equality-delete CDC path, and three distribution modes: `NONE` (default), `HASH`, `RANGE`. All of them are exactly-once for the final Iceberg table state, because they all funnel through the same checkpoint-driven atomic snapshot commit. The distinction that matters for a CDC pipeline is not the mode's checkpoint guarantee (identical across modes) but idempotency under source-level redelivery: only upsert (and the equality-delete CDC path) deduplicates by key, so only those converge if Debezium redelivers a record, which Flink's own docs say it can.**

Plain-English points:

1. **Write modes.** DataStream: `overwrite(boolean)` and `upsert(boolean)` on the `IcebergSink` / `FlinkSink` builder, both default false; append is the absence of both; `equalityFieldColumns(...)` alone is the CDC path. SQL: `INSERT INTO` (append), `INSERT OVERWRITE` (overwrite, batch only), and upsert via `PRIMARY KEY ... NOT ENFORCED` plus `write.upsert.enabled=true` or the `upsert-enabled` option/hint.
2. **Distribution modes.** `DistributionMode.NONE` / `HASH` / `RANGE`, default `none`; SQL exposes them as `distribution-mode` / table property `write.distribution-mode`. The 1.11.0 docs still say RANGE is missing from `IcebergSink`; the code and the 1.10.0 release notes say otherwise. Trust the code.
3. **Failure semantics.** Records after the last completed checkpoint are written as temporary files and are not in the table; on restart the source replays them and the sink commits them. Replay does not duplicate rows, because each commit stamps `flink.max-committed-checkpoint-id` (with job id and operator id) into the snapshot summary and the committer only commits checkpoint ids greater than that. This holds for every mode.
4. **Exactly-once scope.** The documented claim, "The Flink Iceberg sink guarantees exactly-once semantics", is exactly-once for the table commit. End-to-end exactly-once also needs a replayable source and a durable checkpoint, and the docs themselves note commits can fail while checkpoints succeed. No mode is documented as at-least-once.
5. **Upsert / CDC.** Requires v2 (or v3) format and equality fields (primary key or identifier fields); upsert is turned on by `write.upsert.enabled=true` or `upsert-enabled=true`. An update on disk is a key-only equality-delete record plus a full-row data record in the same `RowDelta`; a delete is a key-only equality delete. Same-key repeats inside one writer collapse to a position delete, and cross-commit deletes work because an equality delete only applies to data files with a strictly lower sequence number.
6. **Commit protocol.** One atomic Iceberg commit per checkpoint in the CDC/upsert path (per-checkpoint `RowDelta`), or one merged append commit covering several checkpoints in append mode. The committer is a single Flink subtask; the atomic point is Iceberg's metadata-file swap, so concurrent readers are safe. There is no cross-system XA: the "two-phase" is Flink's checkpoint-then-commit, made idempotent by the snapshot summary. A crash after the checkpoint but before the commit is repaired on restore, which commits the pending tail. Losing sink state (`--allowNonRestoredState` with a changed uid) is the documented way to lose data.

**Confidence: high** for (a), (d) and (e), where I read the 1.11.0 code line by line and the spec owns the delete-application rule. **High** for (c) as a statement of what is documented, and **medium-high** for the end-to-end interpretation, since that rests on Flink's checkpoint/2PC contract which I read only at the interface level. **Medium** for (b)'s per-mode nuances, because the "upstream duplicate in append mode" consequence is my inference from the Debezium at-least-once statement rather than an Iceberg-documented caveat.

**What would raise it:** (1) a Flink SinkV2 / FLIP-191 primary statement on exactly when `Committer#commit` is invoked, closing the one UNVERIFIED item; (2) an end-to-end integration test against the target stack (Kafka Debezium -> Flink upsert -> Iceberg) that kills the job between checkpoint and commit and asserts a single row per key; (3) reading the Iceberg integration tests `TestFlinkIcebergSinkV2` / `TestIcebergCommitter` at 1.11.0 to confirm the restore-and-commit path is exercised for the equality-delete case specifically.
