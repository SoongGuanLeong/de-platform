# 18 - Can the Flink and Spark Iceberg connectors write format v3?

**Date of research:** 2026-09-28. All evidence accessed 2026-09-28 unless stated.
**Scope:** whether the Apache Iceberg Flink connector (DataStream / Table API sink) and the Apache Iceberg Spark connector can write Iceberg format-version 3 tables, and specifically whether the Flink upsert path the platform's streaming design uses (ADR-0013) still holds on v3.
**Question answered:** for the platform's pinned set (Apache Iceberg 1.11.0, Apache Flink 2.1.3, Apache Spark 4.1.3, per ADR-0024), can Flink and Spark write v3, can Flink upsert on v3, what happens to the equality-delete upsert path on v3, is there a documented engine support matrix, and is there a known writer-to-reader gap.
**Exact version read:** Apache Iceberg **1.11.0**, git tag `apache-iceberg-1.11.0`, published **2026-05-20** [S1]. Flink facts are read from the `flink/v2.1` module, which is the module that serves the pinned Flink 2.1 line. Spark facts are read from the `spark/v4.1` module. Both were read from a sparse checkout of the tag, not from a branch.

This document deliberately separates four kinds of claim, because on this question they disagree: (i) what the Iceberg documentation states, (ii) what the connector source does, (iii) what the connector's own tests exercise, and (iv) what I infer. Where documentation and code disagree I say so and prefer the code, as research 06 and 10 do.

---

## 1. What "writing v3" requires

Format v3 is defined in the spec [S8]. Its writer-visible changes that matter for a CDC upsert path are:

- **Deletion vectors replace position delete files.** Position deletes are encoded in a position delete file in v2, or in a deletion vector in v3 or above [S8]. Appendix E is explicit: "Deletion vectors are added in v3, stored using the Puffin `deletion-vector-v1` blob type" and "Writers are not allowed to add new position delete files to v3 tables" [S8]. A v3 writer that emits a position delete file is therefore non-conformant, not merely old-fashioned.
- **Equality deletes are unchanged.** Appendix E's Version 3 changes do not mention equality delete files [S8]. Equality deletes remain a valid v3 delete encoding, written as equality delete files.
- **Row lineage becomes mandatory.** "In v3 and later, an Iceberg table must track row lineage fields for all newly created rows. Engines must maintain the `next-row-id` table field" [S8]. Snapshots must set `first-row-id`, manifests must be assigned `first_row_id`, and new data files are written with a null `first_row_id` that is inherited at read time [S8].
- **Default values and new types.** `initial-default` / `write-default` and the `variant`, `geometry`, `geography`, `unknown`, `timestamp_ns`, `timestamptz_ns` types are v3 [S8].

So "can write v3" is not one property. It decomposes into: writes DVs instead of position delete files; keeps equality deletes working; and participates in row lineage. The rest of this document checks each.

---

## 2. Question 1: does the Flink sink write v3, and does it upsert on v3?

### 2.1 What the documentation states

The Flink writes page at tag 1.11.0 documents upsert as v2 only, three times, with no v3 allowance:

- "Iceberg supports `UPSERT` based on the primary key when writing data into v2 table format." [S2]
- "Note that you still need to use v2 table format and specify the primary key or identifier fields when creating the table." [S2]
- "Set the `upsert` flag in FlinkSink builder to upsert the data in existing iceberg table. The table must use v2 table format and have a primary key." [S2]

Every DDL example in `flink-ddl.md` that declares a primary key uses `format-version`=`2` [S3]. The only v3 statement anywhere in the Flink docs is a dynamic-sink caveat: "Dynamic sink does not support upgrading a table with dynamic records. The job should not be running while the V2 to V3 upgrade is in progress." [S2]

There is **no documentation statement at 1.11.0 that the Flink sink supports v3 at all**, for append or for upsert. The docs are silent on v3 write support, not permissive and not prohibitive.

### 2.2 What the source does

The source is format-version aware and has no v2 guard on upsert:

- `RowDataTaskWriterFactory.initialize` sets `this.useDv = TableUtil.formatVersion(table) > 2` [S4]. On a v3 table the delta writers are built with `useDv=true`.
- `BaseDeltaTaskWriter` passes `useDv` to `BaseTaskWriter`, whose constructor creates a `PartitioningDVWriter` when `useDv` is true [S5], [S6]. That is the code path that writes deletion vectors instead of position delete files.
- The equality-delete path is unchanged: `BaseDeltaTaskWriter.write` still calls `deleteKey` / `delete` and writes equality delete files [S5]. On v3 the same-key-within-one-writer collapse, which in v2 used a position delete, goes through the DV writer [S5], [S6].
- Nothing rejects v3. `IcebergSink.Builder.build()` validates overwrite/upsert exclusivity, non-empty equality fields, and partition fields being a subset of equality fields, but does not check the format version [S6]. `FlinkWriteConf.upsertMode()` reads only the write option, the Flink config and the table property `write.upsert.enabled`, with no version check [S7].
- `FlinkManifestUtil` threads the table's format version into `ManifestFiles.write` / `ManifestFiles.writeDeleteManifest`, so manifests are written with the correct version and the core library owns `first_row_id` assignment [S5]. `TableUtil.supportsRowLineage(table)` exists in core and is `formatVersion >= TableMetadata.MIN_FORMAT_VERSION_ROW_LINEAGE` [S9].

**Reading:** the Flink sink is implemented to write v3 correctly, including the mandatory DV substitution, and upsert is not gated on v2 in code. The v2-only wording in the docs is not enforced.

### 2.3 What the tests exercise

This is where the answer narrows.

| Test | Format version exercised | What it covers |
|---|---|---|
| `TestIcebergSinkV2` | v2 only (`TableProperties.FORMAT_VERSION` = `"2"`) [S17] | SinkV2 append, distribution modes |
| `TestFlinkIcebergSinkV2Base` (upsert tests) | v2 only, via the v2 table above [S18] | `testUpsertOnIdDataKey`, `testUpsertOnDataKey`, `testUpsertOnIdKey` |
| `TestIcebergSinkBranch` / `TestIcebergSinkV2Branch` | v1 and v2 [S17] | branch writes |
| `TestIcebergCommitter` | `TestHelpers.ALL_VERSIONS` = 1 to 4 [S19], [S22] | committer commit of data and delete files; `testDeleteFiles` runs for version >= 2 [S19] |
| `TestDynamicIcebergSink` | v3 (`TableProperties.FORMAT_VERSION` = `"3"`) [S20] | dynamic multi-table sink, multi-format-version |
| `TestIcebergSourceReaderDeletes`, `TestFlinkInputFormatReaderDeletes` | `DeleteReadTests` parameters include `{PARQUET, 3}` [S21] | Flink readers apply deletes, including a v3 deletion vector |

So:

- The **upsert** tests are v2 only. I found no Flink test at 1.11.0 that runs upsert mode against a v3 table. The only Flink tests that touch v3 writes are the dynamic sink and the committer.
- The committer test covers v3 commit of delete files (`testDeleteFiles` for version >= 2), which is the commit half of the path.
- The reader tests cover v3 delete reads.

### 2.4 Answer to question 1

**Flink append/overwrite on v3: implemented, undocumented, and not integration-tested at the sink level in 1.11.0.** The writer is version-aware and the core library handles row lineage; the sink's own integration tests are v1/v2.

**Flink upsert on v3: implemented in code, undocumented, and not integration-tested, therefore unverified.** The only three things that decide whether it is *supported* are: the docs say v2 (they do not mention v3); the code has no v2 guard and takes the DV path (it does); and a test proves it (none does). On the platform's evidence standard this is a documented gap, not a supported capability. The falsifiable next step is to run `TestFlinkIcebergSinkV2Base.testUpsertOnIdKey` (and the partitioned and data-key variants) with `FORMAT_VERSION` = 3 and `useDv` on, then read the table back and assert one live row per key.

---

## 3. Question 2: what happens to the equality-delete upsert path on v3 (ADR-0013)

ADR-0013 designs the CDC job so that the stream reaching the sink is LSN-monotonic per key, and relies on the sink's key-only equality delete plus new row, so that last committed write wins and highest LSN wins coincide. The relevant question is whether v3 changes that.

**v3 does not change equality deletes.** The spec keeps equality delete files as a delete encoding [S8]. The application rule is also unchanged: an equality delete applies to a data file only when "the data file's data sequence number is *strictly less than* the delete's data sequence number" [S8]. That is exactly the rule ADR-0013's convergence argument depends on, and it is the same in v2 and v3.

**v3 changes only the position-delete side of the same-commit collapse.** In v2, when the same key is written twice inside one writer, `BaseEqualityDeltaWriter` collapses it with a position delete pointing at the earlier row. On v3 that position delete must be a deletion vector, and the code does that via `useDv` [S4], [S5], [S6]. The cross-commit deletes remain equality deletes.

**v3 forbids new position delete files**, so the `useDv` switch is mandatory, not an optimisation: "Writers are not allowed to add new position delete files to v3 tables" [S8].

**Row lineage explicitly excludes equality-delete updates.** The spec: "Row lineage does not track lineage for rows updated via Equality Deletes, because engines using equality deletes avoid reading existing data before writing changes and can't provide the original row ID for the new rows. These updates are always treated as if the existing row was completely removed and a unique new row was added." [S8] This is a lineage semantics statement, not a correctness problem for convergence.

**Net effect on ADR-0013:** the design survives a move to v3 unchanged in its convergence argument. The only mechanical difference is that the same-commit collapse writes a deletion vector instead of a position delete file. ADR-0013's text ("the sink's key-only equality-delete path is what the operator feeds", "Format version 2") would need its format-version sentence revisited if the platform moved to v3, but the ordering argument does not.

**One conversion feature is not in 1.11.0.** Iceberg 1.12.0 adds a Flink maintenance task, `ConvertEqualityDeletes`, that rewrites equality deletes into deletion vectors so readers apply deletes by position instead of joining against delete files [S25]. PR apache/iceberg#16948 states "Flink's upsert mode writes equality deletes, which are cheap to produce but force every reader to join the data against the delete files (merge-on-read)" and "The table must be V3 for deletion vectors" [S25]. It merged 2026-06-25 into the 1.12.0 milestone, after the 1.11.0 release, so it is not available to the pinned set. On 1.11.0 a v3 upsert table still carries equality deletes that every reader must merge on read.

---

## 4. Question 3: does the Spark writer write v3?

**Yes, in the `spark/v4.1` module of Iceberg 1.11.0, and it is tested at v3.**

- `SparkWriteConf.deleteFileFormat()` returns `FileFormat.PUFFIN` when `TableUtil.formatVersion(table) >= 3`, before consulting `write.delete.format.default` [S13]. The delete file format is forced, not configurable, on v3.
- `SparkPositionDeltaWrite.Context.useDVs()` is defined as `deleteFileFormat == FileFormat.PUFFIN`, so the merge-on-read row-level writer takes the DV path on v3 [S14].
- `SparkPositionDeletesRewrite` likewise switches to Puffin for version >= 3 [S14].
- Spark's own v3 writer test exists: `TestDeleteFrom.truncateWithDVs` requires `formatVersion >= 3`, creates the table with `write.delete.mode` = `merge-on-read`, runs `DELETE FROM`, and asserts `SnapshotSummary.ADDED_DVS_PROP` = 1 [S15]. `TestDeleteFrom` is parameterised over `TestHelpers.V2_AND_ABOVE` = 2 to 4 [S15], [S22].
- `TestRewritePositionDeleteFilesAction.testRewriteV2PositionDeletesToV3DVs` upgrades a table to v3 and asserts the rewritten delete files are Puffin [S16].
- The Spark reader is tested over the same version range: `TestSparkReaderDeletes` is parameterised over `V2_AND_ABOVE` for Parquet [S21].

**Connector and version:** the pinned Spark 4.1 line is served by `org.apache.iceberg:iceberg-spark-runtime-4.1_2.13:1.11.0`, which resolves on Maven Central (HTTP 200 on 2026-09-28) [S27]. `spark-core_2.13` 4.1.3 was published to Maven Central on 2026-07-12 [S26].

**Caveat on MERGE INTO.** `spark-writes.md` states that Spark "supports `MERGE INTO` by rewriting data files that contain rows that need to be updated in an `overwrite` commit" [S30]. That is the default copy-on-write behaviour; the DV path above is reached only when the row-level operation is configured merge-on-read (`write.delete.mode` / `write.merge.mode` = `merge-on-read`). So "Spark writes v3" is true, and whether a given Spark operation emits DVs depends on the configured delete mode, not on the format version alone.

**Spark has no equality-delete writer.** Consistent with research 10, the Spark row-level writer emits position deletes (DVs on v3); it does not write equality delete files. That matters for the platform because ADR-0013's convergence mechanism is equality-delete based and belongs to Flink, not Spark.

---

## 5. Question 4: does Iceberg document an engine support matrix for v3?

**No.** At tag 1.11.0 there is no engine-by-format-version support matrix anywhere in `docs/docs`:

- `index.md` names the engines ("Spark, Trino, PrestoDB, Flink, Hive and Impala") but says nothing about format versions [S24].
- `configuration.md` documents `format-version` with a default of 2 and links to the spec [S23]. It does not list which engines can write 3.
- `flink-writes.md` and `spark-writes.md` do not state v3 write support at all; `flink-writes.md` still frames upsert as v2 [S2], [S30].
- The spec's Format Versioning section explains the version semantics and says tables "may continue to be written with an older version of the spec to ensure compatibility by not using features that are not yet implemented by processing engines" [S8]. That is a design principle, not a matrix.

The consequence is that engine support must be established from code and tests, engine by engine and feature by feature, which is what Sections 2 to 4 do. Anyone looking for a single authoritative v3 support table at 1.11.0 will not find one, and should not cite one.

---

## 6. Question 5: known gaps where a writer produces v3 that a reader cannot consume

**6.1 The decisive gap is the serving reader, not the writers (cross-reference).** The pinned serving reader, ClickHouse 26.8 LTS, cannot read v3 deletion vectors; ADR-0022 records this as the reason v2 is pinned. A v3 table written by Flink or Spark emits deletion vectors for the operations that produce them (Flink same-key-within-commit collapse; Spark merge-on-read deletes and merges [S5], [S13], [S15]), and the platform's M2 convergence test feeds a deliberately shuffled and duplicated stream, which is precisely the input that triggers the Flink collapse [S6]. So moving the facts to v3 would break the read-through arm. This is owned by the v3 stack review (issue #22) and by ADR-0022; it is a reader gap, and the write side is not the constraint.

**6.2 Flink and Spark readers do consume v3 that Flink and Spark write.** The Flink reader is tested against a v3 deletion vector (`DeleteReadTests` includes `{PARQUET, 3}`, and `FileHelpers.writeDeleteFile` writes a DV for version >= 3) [S21], and the Spark reader is tested over `V2_AND_ABOVE` [S21]. So there is no Iceberg-reader-side gap for a Flink- or Spark-written v3 table; the gap is with readers outside the Iceberg connectors, ClickHouse being the one the platform pins.

**6.3 Flink compaction: one API rejects v3, another supports it.** `RewriteDataFilesAction` rejects v3 outright: `Preconditions.checkArgument(!TableUtil.supportsRowLineage(table), "Flink does not support compaction on row lineage enabled tables (V3+)")` [S10]. The newer maintenance operator does support it: `DataFileRewriteRunner` computes `preserveRowId = TableUtil.supportsRowLineage(value.table())` and reads and writes with `MetadataColumns.schemaWithRowLineage` when true [S11]. So a v3 table can be compacted through the maintenance operator but not through the older action. A design that named `RewriteDataFilesAction` as the Flink compaction path would need to move to the maintenance operator before v3.

**6.4 Concurrent v2 to v3 upgrade during a running upsert job can produce a non-conformant v3 table.** The writer computes `useDv` once, in `RowDataTaskWriterFactory.initialize` [S4]. If the table is upgraded to v3 while the job is running, the writer keeps `useDv=false` and continues to write position delete files, which the spec forbids on v3 [S8]. The **dynamic** sink guards against this in `DynamicCommitter`: if the table version is > 2 and any pending delete file is a non-DV position delete, it fails with "Can't add position delete file to the %s table. Concurrent table upgrade to V3 is not supported." [S12]. The legacy `IcebergFilesCommitter` and the SinkV2 `IcebergCommitter` have no equivalent guard; they pass the table's format version to manifest writing but never inspect delete file content [S5]. So for the legacy/SinkV2 sink the mitigation is operational: stop the upsert job before upgrading the table, or route through a branch and promote (ADR-0016's pattern) rather than upgrading in place under a running writer.

**6.5 Not a v3-specific bug, but adjacent.** Iceberg issue #17615 (open at the time of writing) reports "Flink: DynamicIcebergSink throws UnsupportedOperationException for VARIANT columns" [S29]. This concerns the v3 `variant` type in the dynamic sink, not the upsert path, and is recorded only so that a v3 move does not treat the dynamic sink as uniformly v3-ready.

---

## 7. Verdict for the pinned set

- The write side is **not** the blocker for v3. Both connectors in Iceberg 1.11.0 contain v3-aware writers that switch to deletion vectors and participate in row lineage through the core library.
- Flink **append** on v3 is implemented but undocumented and untested at the sink integration level in 1.11.0.
- Flink **upsert** on v3 is implemented but undocumented and untested, so it is **unverified**. The ADR-0013 convergence argument is unaffected by v3 in principle; the missing evidence is a test, not a design flaw.
- Spark writes v3, is tested at v3, and its delete-file format is forced to Puffin on v3.
- There is no Iceberg engine support matrix to cite. Support has to be argued from code and tests.
- The blocking gap remains the pinned serving reader (ClickHouse 26.8 LTS cannot read v3 DVs, ADR-0022), plus two operational gaps (Flink `RewriteDataFilesAction` rejects v3; the legacy/SinkV2 committer has no concurrent-upgrade guard) and one missing capability (equality-delete to DV conversion is 1.12.0 only).

**Re-review triggers.** Re-run this assessment when (a) ClickHouse 27.3 LTS ships and can read v3 deletion vectors, so the read-through constraint in ADR-0022 lifts; and (b) a Flink upsert-on-v3 integration test exists at the pinned Iceberg tag, which would convert question 1 from unverified to supported. Until both hold, ADR-0022's v2 pin stands on the reader, and the v3 stack review should record Flink v3 upsert as unverified rather than supported.

---

## 8. What I could not verify

- **Flink upsert on v3 end to end.** No integration test exists at tag 1.11.0, and I did not run one. The code path is present and has no v2 guard, but "present in source" is not "proven to converge". This is the single most important unverified item.
- **Whether the Flink SinkV2 committer would reject a position delete file on a v3 table.** I read `IcebergCommitter` and `IcebergFilesCommitter` and found no such check [S5], but I did not run a concurrent-upgrade scenario to observe the failure, so the consequence in Section 6.4 is a code reading, not an observed failure.
- **Exact per-minor Flink module mapping** (which of `flink/v1.20`, `v2.0`, `v2.1` serves which Flink release) is taken from ADR-0024 and the module directory layout, not from a release note read end to end. It does not change the answer because the pinned module is `flink/v2.1` either way.
- **Spark MERGE INTO on v3 specifically.** I verified the DV path via `DELETE FROM` and the position-delete rewrite tests [S15], [S16], and the forced Puffin delete format [S13]. I did not find a Spark test that runs `MERGE INTO` with merge-on-read on a v3 table, so the merge-on-read merge case on v3 is inferred from the shared delete-file format, not directly tested.

---

## Sources

All accessed 2026-09-28. "tag 1.11.0" means `apache-iceberg-1.11.0`. Code and docs URLs are at that tag.

- **S1.** Iceberg release list (GitHub REST API): tag `apache-iceberg-1.11.0`, published 2026-05-20T08:47:57Z. https://api.github.com/repos/apache/iceberg/releases
- **S2.** Iceberg docs, "Flink Writes" (`docs/docs/flink-writes.md`), tag 1.11.0: UPSERT as v2, primary key requirement, DataStream upsert as v2, dynamic-sink V2 to V3 upgrade caveat. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/docs/docs/flink-writes.md
- **S3.** Iceberg docs, "Flink DDL" (`docs/docs/flink-ddl.md`), tag 1.11.0: primary key and format-version 2 examples. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/docs/docs/flink-ddl.md
- **S4.** `flink/v2.1/flink/src/main/java/org/apache/iceberg/flink/sink/RowDataTaskWriterFactory.java`, tag 1.11.0: `useDv = TableUtil.formatVersion(table) > 2`. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.1/flink/src/main/java/org/apache/iceberg/flink/sink/RowDataTaskWriterFactory.java
- **S5.** `flink/v2.1` sink sources, tag 1.11.0: `BaseDeltaTaskWriter.java`, `UnpartitionedDeltaWriter.java`, `PartitionedDeltaWriter.java`, `FlinkManifestUtil.java`, `IcebergFilesCommitter.java`, `IcebergCommitter.java`, `IcebergWriteAggregator.java`. https://github.com/apache/iceberg/tree/apache-iceberg-1.11.0/flink/v2.1/flink/src/main/java/org/apache/iceberg/flink/sink
- **S6.** `core/src/main/java/org/apache/iceberg/io/BaseTaskWriter.java`, tag 1.11.0: `if (useDv) { this.dvFileWriter = new PartitioningDVWriter<>(...); }`, and `IcebergSink.java` build validations. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/core/src/main/java/org/apache/iceberg/io/BaseTaskWriter.java and https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.1/flink/src/main/java/org/apache/iceberg/flink/sink/IcebergSink.java
- **S7.** `flink/v2.1/flink/src/main/java/org/apache/iceberg/flink/FlinkWriteConf.java`, tag 1.11.0: `upsertMode()` reads write option, Flink config and `TableProperties.UPSERT_ENABLED`, no version check. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.1/flink/src/main/java/org/apache/iceberg/flink/FlinkWriteConf.java
- **S8.** Iceberg format specification (`format/spec.md`), tag 1.11.0: Format Versioning; Version 3; row-level deletes (position deletes as file in v2 or deletion vector in v3+; equality delete files); scan planning delete scope rules (equality delete strictly less than, DV less than or equal to); Row Lineage (equality deletes excluded); Appendix E Version 3 (DVs in Puffin, writers may not add position delete files to v3, row lineage writer obligations). https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/format/spec.md
- **S9.** `core/src/main/java/org/apache/iceberg/TableUtil.java`, tag 1.11.0: `formatVersion(table)`, `supportsRowLineage(table)`. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/core/src/main/java/org/apache/iceberg/TableUtil.java
- **S10.** `flink/v2.1/flink/src/main/java/org/apache/iceberg/flink/actions/RewriteDataFilesAction.java`, tag 1.11.0: rejects v3. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.1/flink/src/main/java/org/apache/iceberg/flink/actions/RewriteDataFilesAction.java
- **S11.** `flink/v2.1/flink/src/main/java/org/apache/iceberg/flink/maintenance/operator/DataFileRewriteRunner.java`, tag 1.11.0: row lineage preserved on rewrite. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.1/flink/src/main/java/org/apache/iceberg/flink/maintenance/operator/DataFileRewriteRunner.java
- **S12.** `flink/v2.1/flink/src/main/java/org/apache/iceberg/flink/sink/dynamic/DynamicCommitter.java`, tag 1.11.0: concurrent V2 to V3 upgrade guard. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.1/flink/src/main/java/org/apache/iceberg/flink/sink/dynamic/DynamicCommitter.java
- **S13.** `spark/v4.1/spark/src/main/java/org/apache/iceberg/spark/SparkWriteConf.java`, tag 1.11.0: `deleteFileFormat()` returns PUFFIN for version >= 3. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/spark/v4.1/spark/src/main/java/org/apache/iceberg/spark/SparkWriteConf.java
- **S14.** `spark/v4.1/spark/src/main/java/org/apache/iceberg/spark/source/SparkPositionDeltaWrite.java` and `SparkPositionDeletesRewrite.java`, tag 1.11.0: `useDVs() = deleteFileFormat == PUFFIN`, Puffin for version >= 3. https://github.com/apache/iceberg/tree/apache-iceberg-1.11.0/spark/v4.1/spark/src/main/java/org/apache/iceberg/spark/source
- **S15.** `spark/v4.1/spark/src/test/java/org/apache/iceberg/spark/sql/TestDeleteFrom.java`, tag 1.11.0: `truncateWithDVs` requires formatVersion >= 3, sets merge-on-read, asserts `ADDED_DVS_PROP` = 1; parameterised over `TestHelpers.V2_AND_ABOVE`. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/spark/v4.1/spark/src/test/java/org/apache/iceberg/spark/sql/TestDeleteFrom.java
- **S16.** `spark/v4.1/spark/src/test/java/org/apache/iceberg/spark/actions/TestRewritePositionDeleteFilesAction.java`, tag 1.11.0: `testRewriteV2PositionDeletesToV3DVs`. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/spark/v4.1/spark/src/test/java/org/apache/iceberg/spark/actions/TestRewritePositionDeleteFilesAction.java
- **S17.** Flink sink tests, tag 1.11.0: `TestIcebergSinkV2.java` and `TestIcebergSinkV2Branch.java` (FORMAT_VERSION 2), `TestIcebergSinkBranch.java` (FORMAT_VERSION 1). https://github.com/apache/iceberg/tree/apache-iceberg-1.11.0/flink/v2.1/flink/src/test/java/org/apache/iceberg/flink/sink
- **S18.** `TestFlinkIcebergSinkV2Base.java`, tag 1.11.0: `testUpsertOnIdDataKey`, `testUpsertOnDataKey`, `testUpsertOnIdKey`. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.1/flink/src/test/java/org/apache/iceberg/flink/sink/TestFlinkIcebergSinkV2Base.java
- **S19.** `TestIcebergCommitter.java`, tag 1.11.0: parameterised over `TestHelpers.ALL_VERSIONS`; `testDeleteFiles` assumes version >= 2. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.1/flink/src/test/java/org/apache/iceberg/flink/sink/TestIcebergCommitter.java
- **S20.** `TestDynamicIcebergSink.java`, tag 1.11.0: `FORMAT_VERSION` = 3, `testMultiFormatVersion`. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.1/flink/src/test/java/org/apache/iceberg/flink/sink/dynamic/TestDynamicIcebergSink.java
- **S21.** Delete read tests, tag 1.11.0: `data/src/test/java/org/apache/iceberg/data/DeleteReadTests.java` parameters include `{PARQUET, 3}`; Flink `TestIcebergSourceReaderDeletes` and `TestFlinkInputFormatReaderDeletes` extend it; Spark `TestSparkReaderDeletes` parameterised over `TestHelpers.V2_AND_ABOVE`. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/data/src/test/java/org/apache/iceberg/data/DeleteReadTests.java
- **S22.** `api/src/test/java/org/apache/iceberg/TestHelpers.java`, tag 1.11.0: `MAX_FORMAT_VERSION = 4`, `ALL_VERSIONS` = 1 to 4, `V2_AND_ABOVE` = 2 to 4. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/api/src/test/java/org/apache/iceberg/TestHelpers.java
- **S23.** Iceberg docs, "Configuration" (`docs/docs/configuration.md`), tag 1.11.0: `format-version` default 2; `write.delete.mode` merge-on-read is v2 and above. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/docs/docs/configuration.md
- **S24.** Iceberg docs, "Introduction" (`docs/docs/index.md`), tag 1.11.0: engine list, no format-version matrix. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/docs/docs/index.md
- **S25.** apache/iceberg PR #16948, "Flink: Add equality delete conversion API and integration tests", merged 2026-06-25, milestone Iceberg 1.12.0: `ConvertEqualityDeletes` rewrites equality deletes to DVs; "The table must be V3 for deletion vectors". https://github.com/apache/iceberg/pull/16948
- **S26.** Maven Central repository directory listings: `org/apache/flink/flink-core/2.1.3/` dated 2026-06-08; `org/apache/spark/spark-core_2.13/4.1.3/` dated 2026-07-12. https://repo1.maven.org/maven2/org/apache/flink/flink-core/2.1.3/ and https://repo1.maven.org/maven2/org/apache/spark/spark-core_2.13/4.1.3/
- **S27.** Maven Central repository directory listings, both HTTP 200 on 2026-09-28: `org/apache/iceberg/iceberg-flink-runtime-2.1/1.11.0/` and `org/apache/iceberg/iceberg-spark-runtime-4.1_2.13/1.11.0/`. https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-flink-runtime-2.1/1.11.0/ and https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-4.1_2.13/1.11.0/
- **S28.** ADR-0022 "Iceberg format v2 is pinned, and v3 is a reviewed gap"; ADR-0024 "Engine pins follow Iceberg's supported connector matrix"; ADR-0013 "Enforce LSN order in a stateful operator, not by keying alone"; ADR-0016 "Gate on input and promote through a branch". Repository files `docs/adr/0022-iceberg-format-v2-is-pinned.md`, `docs/adr/0024-engine-pins-follow-the-iceberg-connector-matrix.md`, `docs/adr/0013-lsn-ordering-in-a-stateful-operator.md`, `docs/adr/0016-gate-on-input-and-promote-through-a-branch.md`.
- **S29.** apache/iceberg issue #17615 (open), "Flink: DynamicIcebergSink throws UnsupportedOperationException for VARIANT columns". https://github.com/apache/iceberg/issues/17615
- **S30.** Iceberg docs, "Spark Writes" (`docs/docs/spark-writes.md`), tag 1.11.0: MERGE INTO rewrites affected data files in an overwrite commit. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/docs/docs/spark-writes.md
