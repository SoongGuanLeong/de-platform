# 16 - ClickHouse and Iceberg v3: deletion-vector read support on the pinned 26.8 LTS

**Date of research:** 2026-09-28. All evidence accessed 2026-09-28 unless stated.
**Scope:** ClickHouse's own source at the current 26.8 LTS patch tag `v26.8.13.2-lts` (published 2026-09-27), the `master` branch as of 2026-09-28, first-party GitHub PRs and issues, release changelogs, and ClickHouse documentation. This note answers the six ClickHouse-side questions raised by ticket #22's serving-arm claim, namely whether the pinned 26.8 LTS can read Iceberg v3 tables and, if not, exactly what fails.
**Question answered:** Can ClickHouse 26.8 LTS read Apache Iceberg v3 tables, and what is the precise feature boundary that makes a read fail.

---

## 1. The direct answers

| # | Question | Answer |
|---|----------|--------|
| 1 | Can 26.8 LTS read v3 deletion vectors, and is the failure a hard error or a fallback? | No. It is a hard error: `BAD_ARGUMENTS: Position deletes are supported only for parquet format`. No silent fallback, no undeleted rows. |
| 2 | Exact version and date the read support landed. | PR #110781 merged 2026-09-17, attributed to `26.10.1.35` and "included in `26.10` and later". The ticket's version is confirmed; 26.10 itself is not yet released as of 2026-09-28. |
| 3 | Next LTS after 26.8 and its expected date. | 27.3, expected late March 2027. LTS releases are published in March and August each year. New features are not backported to 26.8. |
| 4 | Can 26.8 read a v3 table with no deletion vectors? Is format-version the blocker? | Yes, it can. Format-version 3 is not the blocker. Only the Puffin deletion-vector feature fails. One deletion vector in a scanned data file is enough to break a scan. |
| 5 | Does the Iceberg REST catalog (Polaris) path change anything for v3? | No. The catalog resolves metadata and location; data reads use the same Iceberg reader. v3 behavior is a property of the ClickHouse binary version, not the catalog. |
| 6 | Does ClickHouse write to Iceberg? | Yes, but only to standalone (non catalog-managed) Iceberg tables. Catalog-backed tables such as Polaris are read-only. Deletion vectors are not written, updated, or compacted. |

## 2. Q1: 26.8 LTS and v3 deletion vectors, exact behavior

The failure is a hard error, thrown while the query pipeline is being built for a data file that has a deletion vector attached.

- The throw is in `src/Storages/ObjectStorage/DataLakes/Iceberg/PositionDeleteTransform.cpp` at tag `v26.8.13.2-lts`, lines 84 to 86 [S1]:
  ```cpp
  String format = position_deletes_object.file_format;
  if (boost::to_lower_copy(format) != "parquet")
      throw Exception(ErrorCodes::BAD_ARGUMENTS, "Position deletes are supported only for parquet format");
  ```
- 26.8 has no deletion-vector reader at all. The directory `src/Storages/ObjectStorage/DataLakes/Iceberg` at `v26.8.13.2-lts` contains no `DeletionVectorObject.h` and no `IcebergDeletionVectorReader.cpp` or `.h`. All three exist on `master` [S2].
- 26.8's `Constant.h` does not define the v3 fields `content_offset` or `content_size_in_bytes`. `master` defines both [S3].
- 26.8 has no `isDeletionVector()` branch. In `IcebergIterator.cpp` at `v26.8.13.2-lts`, every position-delete manifest entry is turned into a `PositionDeleteObject`. On `master` the iterator checks `isDeletionVector()` and routes Puffin entries to `addDeletionVector()` instead [S5]. The predicate on `master` is `content_type == FileContentType::POSITION_DELETE && toLower(file_format) == "puffin"` [S5].
- Consequence: in 26.8 a Puffin entry is treated as a Parquet position-delete file, the delete transform is constructed, and the non-Parquet check above throws. The query fails. It does not fall back to ignoring the deletes, so it does not silently return wrong results.

Scope of the failure: the error is reached only when the query scans a data file that carries an attached deletion vector. If predicate or partition pruning removes every such data file, or the query only touches metadata (for example `DESCRIBE`), the error is not reached. A plain `SELECT count()` over a table whose current snapshot carries a deletion vector does reach it.

## 3. Q2: exact version and date the read support landed

The ticket's claim of `26.10.1.35` is confirmed, and the merge date is 2026-09-17.

- PR #110781, title "Add support for reading Iceberg v3 deletion vectors", merged 2026-09-17T14:02:53Z, merge commit `e6019455e0df5343f4f8a0c6d8ed64e4387ee707`. Changelog category "Experimental Feature", label `pr-experimental` [S9].
- Issue #107502, title "Support reading Iceberg v3 deletion vectors", was closed on 2026-09-17 as completed. Its own machine-maintained version block reads: "Resolved by: #110781" and "Merged into: `26.10.1.35` (included in `26.10` and later)" [S10].
- An earlier alternative implementation, PR #113561, was created 2026-08-05 and closed unmerged on 2026-09-22. The reviewer asked for #110781 to be merged first [S11].

Caveats on the version claim:

- 26.10 is not yet released as of 2026-09-28. There is no `v26.10.*-stable` GitHub release. The only 26.10 ref is the testing tag `v26.10.1.1-new` [S20]. By the monthly cadence (26.8 LTS on 2026-08-27, 26.9.1 on 2026-09-21, 26.9.3 on 2026-09-26), 26.10 is expected in late October 2026. Treat that date as an inference from cadence, not a published date.
- `26.10.1.35` is the version ClickHouse's automation attributes to the merged commit. It is the first release that will contain it, not a published artifact yet.
- The feature is labelled Experimental, not GA. Even once 26.10 ships, deletion-vector reads carry the experimental label and could change before an LTS.

## 4. Q3: the next LTS after 26.8

The ticket's claim of 27.3 in March 2027 is confirmed as the expected schedule.

- ClickHouse's own backport policy document states: "LTS (Long-Term Support) releases are published in March and August each year. Two LTS versions are supported simultaneously, each for at least 12 months" [S15].
- The observed LTS history matches: 25.3 on 2025-03-20, 25.8 on 2025-08-29, 26.3 on 2026-03-26, 26.8 on 2026-08-27 [S21]. 26.8 is an August LTS, so the next one is 27.3, in March 2027.
- The release call page confirms 26.8 as the LTS: "ClickHouse Release 26.8 LTS", Alexey Milovidov, 2026-08-27 [S22].
- The same backport policy is the load-bearing reason 26.8 will never gain deletion-vector reads: "New features, improvements, performance work - not backported" [S15]. Deletion-vector read support is a new feature, so it will not be cherry-picked onto the 26.8 LTS branch. The earliest LTS that can carry it is 27.3.

Expected date precision: 26.3 landed on 2026-03-26 and 25.3 on 2025-03-20, so late March 2027 is the reasonable expectation. The exact day is unknown until release.

## 5. Q4: a v3 table with no deletion vectors is readable, format-version is not the blocker

This is the critical distinction. ClickHouse reads Iceberg v3 tables that contain no Puffin deletion vectors. The format version alone does not block a read. The blocker is specifically the deletion-vector feature.

Evidence that v3 reading predates 26.8:

- PR #107377, "Tolerate Iceberg v3 reserved row-lineage field ids in native Parquet reader", merged 2026-07-15. Its version block reads "Merged into: `26.7.1.980` (included in `26.7` and later)" and "Backported to: `26.6.3.29`, `26.5.7.43`, `26.3.18.25`" [S12]. The changelog text is: "Fixed reading Iceberg v3 tables whose Parquet data files contain reserved row-lineage columns (such as `_row_id`)". A fix to the v3 read path that was backported as far as 26.3 is direct evidence that v3 tables without deletion vectors were already being read before 26.8.
- Issue #104849, "Support trino in iceberg tests & add test for minimal v3", merged into `26.5.1.854` [S13]. A "minimal v3" test has existed since 26.5.

Evidence from the 26.8 source that there is no format-version read gate:

- `IcebergMetadata.cpp` at `v26.8.13.2-lts` reads `format-version` and uses it in exactly two relevant places. It requires `table_uuid` when `format_version >= 2`, and it rejects `OPTIMIZE TABLE ... MANIFEST` when `format_version >= 3` because "the writer does not yet round-trip the row-lineage `first_row_id`" [S6]. The second is a write-path restriction, not a read restriction.
- Schema parsing uses the v2 method when `format_version == 2` and otherwise falls back v1 then v2, so a v3 table's schema metadata parses [S6].
- 26.8's own writer already handles v3: `MetadataGenerator.cpp` has `if (format_version >= 3)` and sets `first_row_id` [S7]. The default write format is v2, since `iceberg_format_version` defaults to 2 [S7].

Evidence from the master test suite (added with PR #110781):

- `tests/integration/test_storage_iceberg_with_spark/test_position_deletes.py` defines `create_spark_v3_table_without_deletion_vectors`, which creates a Spark table with `'format-version' = '3'` and no deletes. The test `test_v3_tables_without_deletion_vectors_reject_clickhouse_mutations` then reads it and asserts `SELECT count()` equals 100 [S25].
- The same file defines `test_mixed_v2_position_deletes_and_v3_deletion_vectors`, which reads a v3 table that carries both a v2-style Parquet position-delete file and a v3 Puffin deletion vector, and asserts the correct filtered rows [S25]. So v2-style Parquet position deletes inside a v3 table are read correctly.
- The file at `v26.8.13.2-lts` contains only format-version 2 tables and no deletion-vector tests, so these are new with the feature [S25].

The minimum v3 feature set that makes 26.8 fail:

- Exactly one thing: a position-delete manifest entry with `file_format = "puffin"` (a `deletion-vector-v1` blob) in the current snapshot, attached to a data file the query scans. In 26.8 that entry becomes a `PositionDeleteObject`, and the position-delete transform rejects any non-Parquet delete file [S1][S4]. One deletion vector is sufficient to turn a scan into a hard error.

What does not block a read on its own:

- The `format-version: 3` metadata value.
- Parquet data files.
- v2-style Parquet position-delete files and equality-delete files inside a v3 table. Qualification: the Iceberg spec forbids adding new position delete files to v3 tables ("Position delete files must not be added to v3 tables, but existing position delete files are valid"), so this case only arises for tables upgraded from v2 that still carry legacy position delete files. A fresh v3 row-level write produces deletion vectors, not position delete files [S28].
- Row-lineage `first_row_id` fields, which the reader tolerates after PR #107377 [S12]. 26.9 additionally added `first_row_id` and `last_seq_num` as virtual columns (PR #115603) and writing of `next-seq-num` and `first_row_id` statistics (PR #116171) [S24].
- v3 nanosecond timestamp types `timestamp_ns` and `timestamptz_ns`, which the table-engine docs map to `DateTime64(9)` and `DateTime64(9, 'UTC')` and list as "since Iceberg v3 only" [S18]. Issue #97015 tracked reading these types and was closed 2026-03-23 [S14]. Treat this as documentation-derived, not independently tested here.

Confidence and limitation: for 26.8 specifically, the "no deletion vectors means readable" conclusion is source-derived, high confidence, but not executed in this research. The tests cited above run on `master` and 26.9 or later. The falsifiable test in section 8 closes that gap.

## 6. Q5: the Iceberg REST catalog (Polaris) path

The catalog path does not change v3 behavior.

- ClickHouse's Polaris support is the generic Iceberg REST catalog path in the `DataLakeCatalog` database engine with `catalog_type = 'rest'`, not a Polaris-specific connector. The catalog resolves the table's metadata location and optionally vends storage credentials; the data read then goes through the same `StorageObjectStorage` and `IcebergMetadata` code used by the standalone `iceberg` table functions and `IcebergS3` engines. This is established in detail in `docs/research/05-clickhouse-polaris-integration.md` [S27].
- Because the reader is shared, deletion-vector support through a Polaris-backed catalog is exactly the same as through a plain `icebergS3()` read: it depends on the ClickHouse binary version, not on the catalog type.
- The catalog integration itself is Beta and read-only: the support matrix lists Iceberg REST read as Beta and create table and INSERT as no [S16].
- Boundary of this note: whether Polaris 1.7.0 itself serves v3 table metadata is a separate question, owned by ticket #22 item 4 and researched separately. This note establishes only the ClickHouse side.

## 7. Q6: does ClickHouse write to Iceberg

Yes, but only to standalone Iceberg tables, and never deletion vectors.

- ClickHouse's own writing guide states: "Writing to open table formats is currently supported for Iceberg tables only. ... Tables must not be managed by a catalog" [S19]. So a Polaris-backed table is read-only; writes go to `IcebergS3` or `IcebergLocal` engines and the `iceberg` table function.
- Writes are gated by `allow_insert_into_iceberg`, which defaults to false. The setting is new in 25.7 and Beta from 26.2 [S16].
- The default write format version is 2, since `iceberg_format_version` defaults to 2. The writer has explicit v3 handling for row lineage (`if (format_version >= 3)` sets `first_row_id`) [S7], so writing v3 metadata is implemented, but the deletion-vector feature adds no writing.
- Deletion vectors are not written. PR #110781's own body lists as not supported: "Writing Iceberg v3 deletion vectors", "Updating existing deletion vectors", and "Compaction/rewrite of deletion vectors" [S9]. The docs state: "Deletion vector support is read-only" [S17].
- `ALTER TABLE ... DELETE` and `ALTER TABLE ... UPDATE` are rejected on v3 tables on `master`: `Mutations.cpp` throws `NOT_IMPLEMENTED` with "Iceberg DELETE and UPDATE are not supported for format-version 3 tables" when `format_version >= 3` [S8]. Note this rejection is not present in 26.8, whose `Mutations.cpp` only checks `format_version < 2`; the v3 rejection was added later [S8]. So the mutation behavior on v3 tables differs between 26.8 and master.

## 8. What this means for de-platform

- The ticket's ClickHouse-side version facts are correct: 26.8 LTS cannot read v3 deletion vectors; the read support merged 2026-09-17 and is attributed to `26.10.1.35`; the next LTS is 27.3 in March 2027; and new features are not backported to 26.8.
- But the practical constraint is narrower than "ClickHouse cannot read v3". Format-version 3 is not the blocker. Only a table whose current snapshot carries Puffin deletion vectors fails. A v3 table with only Parquet data files, or with v2-style Parquet position deletes, or with equality deletes, is readable on 26.8.
- The spec's rule that v3 writers may not add position delete files means fresh v3 row-level writes always produce deletion vectors. So any v3 table the platform writes with merge-on-read deletes (Flink upsert collapse, Spark merge-on-read) carries a DV, and 26.8 throws on it. The only 26.8-readable v3 tables are those with no deletes at all, or v2-upgraded tables whose legacy position delete files have not yet been superseded by a DV. Cross-reference: docs/research/18-flink-spark-iceberg-v3-write.md.
- This separates two capabilities the v3 grilling should treat differently:
  - "Demonstrate v3 native column defaults (`initial-default` / `write-default`)" needs a v3 table with no deletes. 26.8 can read such a table today.
  - "Demonstrate v3 deletion vectors end to end" needs a ClickHouse with the deletion-vector reader, which as of 2026-09-28 is 26.10 (non-LTS, Experimental, expected late October 2026) or the 27.3 LTS (expected late March 2027).
- Falsifiable test to run against the pinned 26.8 and against 26.10 when it ships. These mirror the master tests in [S25].
  1. Create a v3 table with Spark or PyIceberg and no deletes. Expected on 26.8: `SELECT` returns all rows, no error. If 26.8 errors, the "format-version is not the blocker" claim is falsified.
  2. Create a v3 table with Spark using `'format-version' = '3'` and merge-on-read, then `DELETE` some rows so a `deletion-vector-v1` Puffin blob exists. Expected on 26.8: hard error `BAD_ARGUMENTS: Position deletes are supported only for parquet format`. Expected on 26.10: the correct filtered row set.
  3. Create a v3 table whose deletes are only v2-style Parquet position-delete files, or equality deletes. Expected on 26.8: reads with the deletes applied.
- One thing to pin when comparing: the deletion-vector reader is Experimental, so a 26.10 result is not the same stability commitment as an LTS. If the decision rule is "wait for the LTS", the trigger version is 27.3, not 26.10, unless an experimental feature in a non-LTS is acceptable.

## Sources

All accessed 2026-09-28 unless stated.

| ID | Source | Notes |
|----|--------|-------|
| S1 | ClickHouse source, `src/Storages/ObjectStorage/DataLakes/Iceberg/PositionDeleteTransform.cpp`, tag `v26.8.13.2-lts`, lines 84 to 86, https://github.com/ClickHouse/ClickHouse/blob/v26.8.13.2-lts/src/Storages/ObjectStorage/DataLakes/Iceberg/PositionDeleteTransform.cpp | The exact 26.8 throw: `BAD_ARGUMENTS: Position deletes are supported only for parquet format`. |
| S2 | ClickHouse source, directory `src/Storages/ObjectStorage/DataLakes/Iceberg` at `v26.8.13.2-lts` versus `master` | 26.8 has no `DeletionVectorObject.h`, `IcebergDeletionVectorReader.cpp/.h`; master has all three. |
| S3 | ClickHouse source, `src/Storages/ObjectStorage/DataLakes/Iceberg/Constant.h` at `v26.8.13.2-lts` versus `master` | `content_offset` and `content_size_in_bytes` exist on master only. |
| S4 | ClickHouse source, `src/Storages/ObjectStorage/DataLakes/Iceberg/IcebergDataObjectInfo.cpp` at `v26.8.13.2-lts` | `addPositionDeleteObject` stores the delete file's own `file_format`; no deletion-vector branch. |
| S5 | ClickHouse source, `ManifestFile.cpp` and `IcebergIterator.cpp` at `master` | `isDeletionVector()` predicate (`content_type == POSITION_DELETE && toLower(file_format) == "puffin"`); `addDeletionVector` routing. |
| S6 | ClickHouse source, `src/Storages/ObjectStorage/DataLakes/Iceberg/IcebergMetadata.cpp` at `v26.8.13.2-lts` | `format_version` handling; `table_uuid` required for >= 2; manifest compaction rejected for >= 3; schema parse falls back v1 then v2. |
| S7 | ClickHouse source, `MetadataGenerator.cpp` and `DataLakeStorageSettings.h` at `v26.8.13.2-lts` / `master` | `if (format_version >= 3)` sets `first_row_id`; `iceberg_format_version` default 2. |
| S8 | ClickHouse source, `src/Storages/ObjectStorage/DataLakes/Iceberg/Mutations.cpp` at `v26.8.13.2-lts` versus `master` | master rejects DELETE/UPDATE for `format_version >= 3`; 26.8 only checks `< 2`. |
| S9 | GitHub PR #110781, "Add support for reading Iceberg v3 deletion vectors", merged 2026-09-17T14:02:53Z, https://github.com/ClickHouse/ClickHouse/pull/110781 | Changelog category Experimental Feature; label `pr-experimental`; lists DV writing, updating, and compaction as not supported. |
| S10 | GitHub issue #107502, "Support reading Iceberg v3 deletion vectors", created 2026-06-15, closed 2026-09-17, https://github.com/ClickHouse/ClickHouse/issues/107502 | Version block: "Resolved by: #110781", "Merged into: `26.10.1.35` (included in `26.10` and later)". |
| S11 | GitHub PR #113561, created 2026-08-05, closed unmerged 2026-09-22, https://github.com/ClickHouse/ClickHouse/pull/113561 | Alternative DV implementation; reviewer asked for #110781 to merge first. |
| S12 | GitHub PR #107377, "Tolerate Iceberg v3 reserved row-lineage field ids in native Parquet reader", merged 2026-07-15, https://github.com/ClickHouse/ClickHouse/pull/107377 | Merged into `26.7.1.980`; backported to `26.6.3.29`, `26.5.7.43`, `26.3.18.25`. Proves v3 reading predates 26.8. |
| S13 | GitHub issue #104849, "Support trino in iceberg tests & add test for minimal v3", merged into `26.5.1.854`, https://github.com/ClickHouse/ClickHouse/issues/104849 | A minimal v3 test since 26.5. |
| S14 | GitHub issue #97015, "Support reading Iceberg v3 nanosecond timestamp types", closed 2026-03-23, https://github.com/ClickHouse/ClickHouse/issues/97015 | v3 `timestamp_ns` / `timestamptz_ns` read support. |
| S15 | ClickHouse docs, backport policy, `docs/resources/develop-contribute/contribute/backports.mdx`, https://github.com/ClickHouse/ClickHouse/blob/master/docs/resources/develop-contribute/contribute/backports.mdx | "LTS releases are published in March and August each year"; "New features, improvements, performance work - not backported". |
| S16 | ClickHouse docs, support matrix, `docs/guides/use-cases/data-warehousing/support-matrix.mdx`, https://github.com/ClickHouse/ClickHouse/blob/master/docs/guides/use-cases/data-warehousing/support-matrix.mdx | Format versions row: "v1 and v2 are supported. v3 support is partial: deletion vector reads are supported; manifest compaction isn't supported." Iceberg REST read Beta, create/INSERT no. |
| S17 | ClickHouse docs, iceberg table function, `docs/reference/functions/table-functions/iceberg.mdx`, https://github.com/ClickHouse/ClickHouse/blob/master/docs/reference/functions/table-functions/iceberg.mdx | "Support for v3 is partial: deletion vector reads are supported"; "Deletion vector support is read-only"; DELETE/UPDATE not supported for v3. |
| S18 | ClickHouse docs, iceberg table engine, `docs/reference/engines/table-engines/integrations/iceberg.mdx`, https://github.com/ClickHouse/ClickHouse/blob/master/docs/reference/engines/table-engines/integrations/iceberg.mdx | v3 `timestamp_ns` / `timestamptz_ns` mapping; deletion methods list; `OPTIMIZE TABLE ... MANIFEST` only for v2. |
| S19 | ClickHouse docs, writing data to open table formats, `docs/use-cases/data_lake/guides/writing-data.md`, https://github.com/ClickHouse/ClickHouse/blob/master/docs/use-cases/data_lake/guides/writing-data.md | "Tables must not be managed by a catalog". |
| S20 | GitHub releases, ClickHouse/ClickHouse, https://github.com/ClickHouse/ClickHouse/releases | `v26.8.1.2041-lts` 2026-08-27; `v26.8.13.2-lts` 2026-09-27; `v26.9.4.3-stable` 2026-09-27; no `v26.10.*-stable`; testing tag `v26.10.1.1-new`. |
| S21 | endoflife.date ClickHouse API, https://endoflife.date/api/clickhouse.json | LTS dates: 26.8 (2026-08-27, EOL 2027-08-27), 26.3 (2026-03-26), 25.8 (2025-08-29), 25.3 (2025-03-20). Secondary source. |
| S22 | ClickHouse release call, "ClickHouse: Release 26.8 Call", Alexey Milovidov, 2026-08-27, https://presentations.clickhouse.com/2026-release-26.8/ | "ClickHouse Release 26.8 LTS"; "A long-term support release". |
| S23 | ClickHouse changelog `v26.8.1.2041-lts`, https://github.com/ClickHouse/ClickHouse/blob/master/docs/changelogs/v26.8.1.2041-lts.md | Puffin format added as a standalone input format (PR #103936), not as Iceberg deletion-vector integration. |
| S24 | ClickHouse changelog `v26.9.1.1629-stable`, https://github.com/ClickHouse/ClickHouse/blob/master/docs/changelogs/v26.9.1.1629-stable.md | Iceberg v3 virtual columns `first_row_id` / `last_seq_num` (PR #115603) and v3 statistics writing (PR #116171). No deletion-vector entry. |
| S25 | ClickHouse tests, `tests/integration/test_storage_iceberg_with_spark/test_position_deletes.py` on `master` versus `v26.8.13.2-lts` | master has `create_spark_v3_table_without_deletion_vectors`, `test_v3_tables_without_deletion_vectors_reject_clickhouse_mutations`, and `test_mixed_v2_position_deletes_and_v3_deletion_vectors`; 26.8 has only v2 tests. |
| S26 | ClickHouse source, `src/Storages/ObjectStorage/DataLakes/Iceberg/IcebergDeletionVectorReader.h` at `master` | `readIcebergDeletionVector(...)` returns `roaring::Roaring64Map`. |
| S27 | Peer research, `docs/research/05-clickhouse-polaris-integration.md` | REST catalog path, Beta, read-only; catalog resolves metadata and location, data reads use the shared object-storage and Iceberg reader. Cross-reference, not independently re-verified here. |
| S28 | Apache Iceberg spec, `format/spec.md` on `main`, https://github.com/apache/iceberg/blob/main/format/spec.md | "Position delete files must not be added to v3 tables, but existing position delete files are valid"; position delete files deprecated in v3; at most one deletion vector per data file per snapshot; writers merge position deletes into DVs. |

## Verdict

**26.8 LTS cannot read Iceberg v3 deletion vectors, and it fails hard rather than falling back: `BAD_ARGUMENTS: Position deletes are supported only for parquet format`.** The read support merged 2026-09-17 and is attributed to `26.10.1.35` (included in `26.10` and later); 26.10 is not yet released as of 2026-09-28 and is expected in late October 2026. The next LTS after 26.8 is 27.3, expected late March 2027, and new features are not backported, so 26.8 will never gain this capability.

**But format-version 3 is not the read blocker.** 26.8 has no format-version read gate, v3 reading predates 26.8 (a v3 row-lineage read fix was backported as far as 26.3), and the master test suite reads a v3 table with no deletion vectors and a v3 table with v2-style Parquet position deletes. The single feature that makes a scan fail is a Puffin deletion vector attached to a scanned data file. A v3 table with no deletion vectors, or with only v2-style Parquet or equality deletes, is readable on 26.8.

Confidence: high on the version facts, the hard-error behavior, and the LTS schedule, all of which rest on primary ClickHouse source, PRs, and the project's own backport policy. High but source-derived on "v3 with no deletion vectors is readable on 26.8" specifically, which should be confirmed by running the section 8 test on a pinned 26.8 binary before it is relied on. The most load-bearing single citation is the 26.8 source throw [S1], backed by the absence of the deletion-vector reader at that tag [S2] and the feature's attribution to 26.10 [S9][S10].
