# 15 - Iceberg format v3 in the pinned 1.11.0: spec finalisation, feature GA, and the one-way upgrade

**Date of research:** 2026-09-28. All evidence accessed 2026-09-28 unless stated.
**Scope:** the status of Apache Iceberg format version 3 (the table spec) and its Java implementation in the pinned release, Apache Iceberg **1.11.0**. The specific questions are whether v3 is final, which v3 features are actually shipped and generally available, how native column defaults behave, the exact v2 limitation that blocks `add-required-with-default`, what the v2 to v3 upgrade forecloses, and whether a v3 table can still use v2-style position delete files.
**Question answered:** for a table that is on Iceberg format v2 (per ADR-0022), what does moving to v3 actually change, and which v3 capabilities can be relied on in the pinned version.
**Exact version read:** Apache Iceberg **1.11.0**, git tag `apache-iceberg-1.11.0`, published **2026-05-20** [S1]. The Java facts are read from the source tree at that tag [S6], [S10], [S11], [S13], [S14], [S20]. The specification facts are read from `format/spec.md` at that tag [S2]. Where a claim is about when a feature first appeared, I read the same file at the earlier release tags and say which tag I read.

The pinned engine set is Apache Iceberg 1.11.0, Apache Flink 2.1.3 and Apache Spark 4.1.3, per ADR-0024 [S23]. The format version pin is v2, per ADR-0022 [S22]. This document does not re-decide either pin; it establishes what v3 is, so the two decisions can be checked against the code.

---

## 1. Is the v3 spec final, and which Iceberg version first read and wrote format-version 3?

**The v3 spec is final.** The community adopted it by vote, and the spec text at 1.11.0 states it.

The adoption vote was raised by Ryan Blue on the Iceberg dev list on **2025-05-19**, under the subject `[VOTE] Adopt the v3 spec changes` [S4]. The result was posted on **2025-05-22**: "With 26 +1 votes (11 binding) and no -1 or +0 votes, this passes." [S5]. The vote text is explicit that adoption is a forward-compatibility commitment, not a default change: "Adopting the changes signals that we (the community) intend to support the current set of changes and will maintain forward-compatibility for v3 tables that implement the v3 spec. After adopting the changes, future breaking changes would go into v4." It also states: "Adoption doesn't change the default table version." [S4], [S5].

The spec file was then updated to record that v3 is complete. PR #13175, `Spec: Mark version 3 as completed`, merged **2025-05-29**, and its body points at the same mailing-list vote [S3]. At tag 1.11.0 the spec header reads: "Versions 1, 2 and 3 of the Iceberg spec are complete and adopted by the community. **Version 4 is under active development and has not been formally adopted.**" [S2].

The version at which that final text first shipped in a GA release is **1.10.0 (2025-09-11)**. I read `format/spec.md` at each tag: 1.6.0, 1.7.0, 1.8.0, 1.9.0, 1.9.1 and 1.9.2 all still say "Versions 1 and 2 ... are complete and adopted" and "Version 3 is under active development and has not been formally adopted"; 1.10.0, 1.10.1, 1.10.2 and 1.11.0 say versions 1, 2 and 3 are complete and v4 is under development [S2]. The 1.9.x line is a maintenance branch cut from 1.9.0 (2025-04-28) and did not receive the adoption commit, so the first GA release carrying it is 1.10.0.

**Which version first supported reading and writing format-version 3** is two questions, because the number was accepted before the features were complete:

| Release | Date | What it did for v3 |
|---|---|---|
| 1.7.0 | 2024-11-08 | First release whose Java library accepts `format-version=3`: `TableMetadata.SUPPORTED_TABLE_FORMAT_VERSION` is raised from 2 to 3 at this tag. The release notes list "Add Basic Classes for Iceberg Table Version 3" (#10760, merged 2024-08-01) and "Add default value APIs and Avro implementation" (#9502). At this point the spec still called v3 "under active development". [S6], [S7], [S8], [S21] |
| 1.8.0 | 2025-02-13 | First release with substantive v3 feature read and write: "Support for reading Deletion Vectors" (#11481, merged 2024-11-08), "Support for writing Deletion Vectors" (#11476, merged 2024-11-06), Spark "Support for writing Deletion Vectors for V3 tables" (#11561, merged 2024-12-06), and row lineage metadata fields (#11948, merged 2025-02-01). [S8], [S12], [S15] |
| 1.9.0 | 2025-04-28 | Default values reach `UpdateSchema` (#12211, merged 2025-02-13). [S8], [S17] |
| 1.10.0 | 2025-09-11 | First GA release shipping the spec text that declares v3 complete; row lineage is made always-on for v3 (#12986, merged 2025-05-07). [S2], [S3], [S16] |
| 1.11.0 | 2026-05-20 | The pinned release. Adds Spark 4.0 schema conversion for default values (#14407, merged 2025-10-29) and further row lineage fixes. [S1], [S19] |

So the precise answer is: **1.7.0 first accepted the `format-version=3` value, 1.8.0 is the first release that could actually read and write the substantive v3 features, and the spec itself was not final until the adoption vote of 2025-05-22, first shipped in 1.10.0.** Any claim that "1.7.0 supports v3" is true only in the narrow sense that the number parses; the features were still landing.

One further fact that matters for scoping: the **default format version is still 2 in 1.11.0**. The configuration reference lists `format-version` with default `2`, and notes it "Defaults to 2 since version 1.4.0" [S9]. v3 is strictly opt-in by setting the table property.

---

## 2. Which v3 features are implemented and GA in 1.11.0?

All three features asked about are implemented in the 1.11.0 Java library. None has a separate feature flag: each is gated only by the table being at format-version 3, which is itself opt-in. The notable incompleteness is in the SQL surface for column defaults, not in the core or the read path.

| v3 feature | Status in 1.11.0 | Gate | Evidence |
|---|---|---|---|
| (a) Native column defaults (`initial-default` / `write-default`) | Implemented and GA in core, API and readers; write-default is surfaced to Spark 4.0+ via Spark default-value metadata. Spark SQL `ALTER TABLE ... ADD COLUMN ... DEFAULT` is explicitly unsupported. | `format-version=3`. `Schema.checkCompatibility` rejects a non-null `initial-default` below v3. | [S10], [S11], [S17], [S18], [S19], [S20] |
| (b) Deletion vectors (DVs) | Implemented and GA: core read and write, Spark writes DVs for v3 merge-on-read tables, Flink writes DVs when the table is above v2. | `format-version=3`, plus a row-level operation in merge-on-read mode (`write.delete.mode` / `write.merge.mode`, default `copy-on-write`). | [S12], [S13], [S14], [S24] |
| (c) Row lineage | Implemented and GA: metadata fields, `next-row-id`, `first-row-id`, `_row_id` and `_last_updated_sequence_number`. It is always on for v3, with no enable step. | `format-version=3`. | [S15], [S16] |

### (a) Native column defaults

The API and core support is complete: `UpdateSchema` exposes `addColumn(..., default)`, `addRequiredColumn(..., default)` and `updateColumnDefault(...)` [S11]; `Schema` version-gates `initial-default` at v3 [S10]; and the schema JSON parser reads and writes both `initial-default` and `write-default` [S2], [S11]. The read path applies `initial-default` in every reader I checked: the core Avro reader (`ValueReaders`), the core Parquet reader (`BaseParquetReaders`), the ORC reader (`ORCSchemaUtil`), the Arrow vectorized reader, and the Spark and Flink Parquet readers [S6 tree].

The write path is where the surface is uneven. `write-default` is consumed by Spark's schema conversion: `TypeToSparkType` maps `write-default` onto Spark's `currentDefaultValue` and `initial-default` onto Spark's `existenceDefaultValue`, which is the Spark 4.0 default-value mechanism [S19], [S20]. On the SQL surface, Spark throws rather than guessing: PR #13464, `Spark: Throw unsupported for ADD COLUMN with default value`, merged **2025-07-07**, shipped in 1.10.0 [S8], [S18]. So the required-with-default capability exists at the Iceberg API level, and is visible to Spark through schema conversion, but you cannot express it through Spark SQL `ALTER TABLE ... ADD COLUMN ... DEFAULT` in 1.11.0.

### (b) Deletion vectors

DVs are a first-class part of v3 and are implemented in core (`DeletionVector`, `DeletionVectorStruct`, `PartitioningDVWriter`, the `deletion-vector-v1` Puffin blob type) [S6 tree]. They are written automatically for v3 tables in both pinned engines:

- Spark: `SparkWriteConf.deleteFileFormat()` returns `FileFormat.PUFFIN` whenever `TableUtil.formatVersion(table) >= 3`, before it looks at any user property [S13].
- Flink: `RowDataTaskWriterFactory` sets `this.useDv = TableUtil.formatVersion(table) > 2` [S14].

DV usage is therefore not a flag you set; it is the consequence of two choices: the table is v3, and the row-level operation runs in merge-on-read mode. The mode is the property that is still opt-in, and its default is `copy-on-write` [S9]. In copy-on-write mode no delete files are produced at all.

### (c) Row lineage

Row lineage was implemented in 1.8.0 (#11948, merged 2025-02-01) [S15]. An early design had an `EnableRowLineage` metadata update (added to the spec in 1.8.0 via #12050), but that was removed: PR #12986, `REST spec: Remove update to enable row lineage`, merged **2025-05-07**, with the release note reading "remove update to enable row lineage as it is always on for V3 table" [S8], [S16]. I confirmed by grep that `EnableRowLineage` no longer exists in the 1.11.0 API or core source. The Java constant `TableMetadata.MIN_FORMAT_VERSION_ROW_LINEAGE` is 3, and `TableMetadataParser` writes `next-row-id` for any metadata with `formatVersion >= 3` [S6]. So a v3 table has row lineage whether or not the writer wants it.

Two caveats are worth recording rather than glossing. First, row lineage is not tracked for rows updated via equality deletes: the spec states "Row lineage does not track lineage for rows updated via Equality Deletes" [S2]. That matters to this platform because the Flink CDC sink writes equality deletes (research 06, research 10). Second, row lineage in the Avro path had defects fixed only in 1.11.0: "Avro: Row Lineage Column (ROW_ID) is not populated correctly in case the Data File doesn't have them" (#15187) and "Avro: Reading files using DataFileStream with ROW LINEAGE fails if the column isn't projected" (#15508) [S1].

### What is behind a flag

Nothing among (a), (b) and (c) sits behind a boolean feature flag. The only gates are the format version (default 2, so v3 is opt-in) and, for DVs, the row-level operation mode (default copy-on-write). That is a cleaner answer than "behind flags": the capabilities are shipped, but they are unreachable on a v2 table by construction.

---

## 3. How do native column defaults behave?

The spec defines two defaults per field [S2], and the code implements that definition.

**`initial-default`** is used "to populate the field's value for all records that were written before the field was added to the schema" [S2]. In practice the readers substitute it at read time for any older data file that lacks the field, so no data files are rewritten. The spec is explicit: "`initial-default` and `write-default` produce SQL default value behavior, without rewriting data files. SQL default value behavior when a field is added handles all existing rows as though the rows were written with the new field's default value." [S2]. The read-side implementation is the constant-fill branch in each reader, for example `BaseParquetReaders`, `ValueReaders`, `ORCSchemaUtil`, `SparkParquetReaders` and `FlinkParquetReaders` [S6 tree].

**`write-default`** is used "to populate the field's value for any records written after the field was added to the schema, if the writer does not supply the field's value" [S2]. The spec makes the writer obligation hard: "The write default for a field must be written if a field is not supplied to a write. If the write default for a required field is not set, the writer must fail." [S2]. In 1.11.0 this is surfaced to Spark through `TypeToSparkType`, which sets Spark's `currentDefaultValue` from `write-default` [S19], [S20].

The two are related but not the same, and the difference is what makes the upgrade safe or unsafe for old readers:

- `initial-default` is set only when a field is added to an existing schema, and it **cannot change** afterwards [S2]. Changing it would change the meaning of already-written rows.
- `write-default` starts equal to `initial-default` and **may change** through schema evolution; a change affects only future records [S2].
- `UpdateSchema.updateColumnDefault` reflects this: its comment in the source reads "write default is always set and initial default is only set if the field requires one", and it only writes `withWriteDefault` [S11].

**Can a column be added as required-with-default? Yes, in v3.** The API is `addRequiredColumn(parent, name, type, doc, default)`, and `internalAddColumn` sets both `withInitialDefault(defaultValue)` and `withWriteDefault(defaultValue)` on the new field [S11]. The reason this is coherent is the initial-default: existing rows are served the default at read time, so a required column can be introduced without rewriting files and without nulls appearing in a required column. The constraint is that the default must be non-null, and the write default must be set, per the spec sentence above.

One structural nuance for nested fields: defaults for a struct's sub-fields are tracked on the sub-fields, not inside the struct's default. A non-null struct default is stored as an empty struct (`{}`) whose effective value is assembled from each sub-field's default [S2].

---

## 4. The exact v2 limitation that prevents add-required-with-default

The limitation is not a policy in `UpdateSchema`; it is a version gate on the schema itself. The mechanism, read at tag 1.11.0:

- `api/src/main/java/org/apache/iceberg/Schema.java` declares `DEFAULT_VALUES_MIN_FORMAT_VERSION = 3` and, inside `Schema.checkCompatibility(Schema, int formatVersion)`, rejects any field whose `initial-default` is non-null when `formatVersion < 3`. The error message is: "Invalid initial default for <column>: non-null default (<value>) is not supported until v3" [S10].
- `Schema.checkCompatibility` is called on every schema update commit: `TableMetadata.Builder.addSchemaInternal` calls `Schema.checkCompatibility(schema, formatVersion)` [S6].
- `SchemaUpdate.internalAddColumn` sets `initial-default` on any column added with a default, including the required case [S11].

So on a v2 table, `addRequiredColumn(name, type, doc, default)` fails at commit with the "not supported until v3" error, because the new field carries a non-null `initial-default`. This is exactly the v2 limitation: **`initial-default` is a v3-only schema attribute, so a required column added to a v2 table has no way to supply a value for rows written before it existed.** Without an initial-default, adding a required column is an incompatible change, which `SchemaUpdate` already refuses with "Incompatible change: cannot add required column without a default value" [S11]. The two guards together leave no v2 path: you cannot add the required column without a default, and you cannot attach the default at v2.

The spec confirms the same limitation from the reader side, in Appendix E: "`initial-default` is a forward-compatible change because it is only used at write time. Old writers will fail because the field is missing. Tables with `initial-default` will be read correctly by older readers if `initial-default` is always null for optional fields. Otherwise, old readers will default optional columns with null. Old readers will fail to read required fields which are populated by `initial-default` because that default is not supported." [S2].

One precision, because it is easy to overstate: `Schema.checkCompatibility` gates `initial-default` only. It does not test `write-default` in the same branch [S10]. The reason this does not create a v2 loophole for the required-column case is that `addRequiredColumn(..., default)` always sets `initial-default`, and it is that field which trips the gate. The repo's ADR-0022 summary, "column defaults are v3-only", is therefore correct for the capability that matters here.

---

## 5. What is irreversible about the v2 to v3 upgrade?

**The format version can never decrease.** `TableMetadata.Builder.upgradeFormatVersion(int)` enforces two preconditions [S6]:

```
Preconditions.checkArgument(
    newFormatVersion <= SUPPORTED_TABLE_FORMAT_VERSION,
    "Cannot upgrade table to unsupported format version: v%s (supported: v%s)", ...);
Preconditions.checkArgument(
    newFormatVersion >= formatVersion,
    "Cannot downgrade v%s table to v%s", formatVersion, newFormatVersion);
```

Setting the `format-version` table property goes through this same path (`TableMetadata` lines that read the property and call `upgradeFormatVersion`), so a request to set it back to 2 raises "Cannot downgrade v3 table to v2" [S6]. There is no supported reversal.

The spec requires the other half: "Implementations must throw an exception if a table's version is higher than the supported version." [S2]. That is what makes the upgrade foreclosing rather than merely recorded.

**What the upgrade forecloses, concretely:**

- **Readers and engines that support only v2 can no longer read the table at all.** They must throw on the version check, not degrade. The table also starts writing v3-only metadata that a v2 parser does not know: `TableMetadataParser` writes `next-row-id` for `formatVersion >= 3` [S6], and the v3 manifest schemas carry `first-row-id`, plus `referenced_data_file`, `content_offset` and `content_size_in_bytes` for DVs [S2]. A v2 reader does not have these fields.
- **Writers that support only v2 can no longer write.** The same version check applies, and v3 additionally forbids new position delete files, so a v2 writer's delete mechanism is not legal on the table [S2].
- **This is the serving-reader problem recorded in ADR-0022.** The platform's serving reader, ClickHouse 26.8 LTS, cannot read v3 deletion vectors, so a v3 CDC fact table would break the read-through arm [S22]. That specific claim is a repo decision about a pinned engine, not an Iceberg spec fact; teammate `clickhouse-v3-read` owns the primary evidence for it, and I did not independently verify ClickHouse's Iceberg read support in this document. What this document establishes is the Iceberg-side mechanism that makes the concern structural: once the table is v3, an engine that cannot parse v3 metadata or DVs cannot fall back.

So the upgrade is a one-way door with two locks: the library refuses to lower the version, and the spec requires every other implementation to refuse to read a version above its support. The consequence is not "v3 tables are unreadable by v2 engines only for the v3 features"; it is "unreadable, full stop", because the version field gates the whole table.

---

## 6. Does v3 still support v2-style position delete files, or must deletes be DVs?

**New position delete files are forbidden in v3; deletes for a v3 table must be deletion vectors, or a mechanism that does not use position deletes at all.** The spec is unambiguous, in the Delete Formats section: "Deletion vectors are added in v3 and are not supported in v2 or earlier. Position delete files must not be added to v3 tables, but existing position delete files are valid." [S2]. The same section lists position delete files as "**deprecated** in v3" [S2]. Appendix E repeats the rule and its migration consequence: "Writers are not allowed to add new position delete files to v3 tables"; "Existing position delete files are valid in tables that have been upgraded from v2"; those must be "merged into the DV for a data file when one is created", and position delete files spanning more than one data file "need to be kept in table metadata until all deletes are replaced by DVs" [S2].

The implementation matches the spec. Spark's write path forces Puffin for v3: `SparkWriteConf.deleteFileFormat()` returns `FileFormat.PUFFIN` for `formatVersion >= 3` before consulting user configuration, and `SparkPositionDeltaWrite` selects `PartitioningDVWriter` when `deleteFileFormat == PUFFIN` [S13]. Flink sets `useDv = formatVersion > 2` in its task writer factory [S14], and its dynamic committer carries the error string "Can't add position delete file to the %s table. Concurrent table upgrade to V3 is not supported." [S6 tree].

**Can a v3 table avoid deletion vectors entirely?** Yes, but only by not using position-based row-level deletes. Three routes exist:

1. **Copy-on-write.** The default row-level operation mode is `copy-on-write` [S9]. A delete or merge rewrites affected data files; no delete files and no DVs are produced. A v3 table with copy-on-write operations has no DVs.
2. **Equality deletes.** Equality delete files identify deleted rows by column value, and they remain valid in v3; only position delete files were deprecated [S2]. This is the route the platform's Flink CDC upsert sink takes: Flink's equality delta writer is selected by `equalityFieldIds` and is separate from the `useDv` delta writer, so an upsert on a v3 table writes key-only equality deletes rather than DVs [S6 tree], [S14]. The trade-off is the row-lineage caveat in section 2: equality-delete updates are not tracked by row lineage [S2]. One application-rule difference matters for upsert semantics: a deletion vector or a position delete file applies to data files whose data sequence number is _less than or equal to_ the delete's, so it can delete rows added in the same commit, while an equality delete file applies only to data files whose data sequence number is _strictly less than_ the delete's [S2].
3. **No deletes.** An append-only v3 table has no DVs, trivially.

What is **not** possible is the v2 pattern of writing new position delete files into a v3 table. That mechanism is closed for new writes. A v3 table upgraded from v2 may still contain v2 position delete files written before the upgrade, but the first DV created for a data file must absorb them [S2].

This matters directly to ADR-0022, which says the CDC facts are merge-on-read. On a v3 table, merge-on-read position deletes are DVs by construction, which is precisely the format the pinned ClickHouse reader cannot read [S22].

---

## 7. What I could not verify, and known discrepancies

- **I did not run any of this.** No v3 table was created, no DV was written, no default was exercised. Every claim is from the spec text, the source at the tag, the project's tracker, or the mailing list. There are no measured numbers in this document.
- **The v3 spec text was final on 2025-05-22 (vote) and 2025-05-29 (spec commit), but the Java implementation had been shipping partial v3 for roughly six months before that.** 1.7.0 (2024-11-08) already accepted `format-version=3`. So "which version first supported v3" depends on whether "supported" means "accepted the number" or "implemented the features". I have given both answers in section 1 rather than collapsing them.
- **I did not audit every v3 feature.** The spec's v3 also adds variant, geometry, geography, unknown, `timestamp_ns` and `timestamptz_ns` types, multi-argument transforms, and table encryption keys [S2], [S4]. The task scoped me to defaults, DVs and row lineage, so I state no GA status for the others. Encryption in particular has `EncryptionUtil.checkCompatibility` and `encryption-keys` metadata in the 1.11.0 source, but I did not establish whether it is usable end to end.
- **The mailing-list pages are JavaScript-rendered on lists.apache.org.** I read the vote and its result from the mail-archive.com mirror of the same `dev@iceberg.apache.org` messages [S4], [S5], which quoted the thread in full. The PR body [S3] links the lists.apache.org thread as the authoritative record; I could not read that page's rendered content directly.
- **`Schema.checkCompatibility` gates `initial-default` only, not `write-default`** [S10]. I have not found a separate check that rejects a lone `write-default` on a v2 table, and I am not claiming one exists. The reason the v2 limitation still holds for add-required-with-default is that the required-with-default API always sets `initial-default` [S11]. If a future reader needs the exact behaviour of a hand-crafted v2 schema carrying only `write-default`, that is unverified here.
- **The ClickHouse constraint is taken from ADR-0022, not verified here.** The statement that ClickHouse 26.8 LTS cannot read v3 deletion vectors is a repo decision [S22]; teammate `clickhouse-v3-read` holds the primary evidence. I cite it only as the motivating consequence, and section 5 states the Iceberg-side mechanism independently.

---

## Sources

All accessed 2026-09-28 unless stated. "tag 1.11.0" means `apache-iceberg-1.11.0`.

| ID | Source | URL | Date |
|---|---|---|---|
| S1 | Apache Iceberg release list; tag `apache-iceberg-1.11.0` published 2026-05-20; 1.10.0 published 2025-09-11; 1.9.0 published 2025-04-28; 1.8.0 published 2025-02-13; 1.7.0 published 2024-11-08. Release bodies also carry the row-lineage Avro fixes #15187 and #15508 | https://api.github.com/repos/apache/iceberg/releases | 2026-09-28 |
| S2 | Iceberg spec, `format/spec.md`, tag 1.11.0: header "Versions 1, 2 and 3 ... are complete and adopted" and "Version 4 is under active development"; Version 3 feature list; Default values (lines 262-286); Schema evolution default rules (lines 326-344); Delete Formats "Position delete files must not be added to v3 tables" and "deprecated in v3" (line 1115); Appendix E Version 3 (lines 1650-1690); table metadata `format-version` "Implementations must throw an exception if a table's version is higher than the supported version" (line 932); Scan Planning scope rules: deletion vector and position delete file apply at data sequence number _less than or equal to_ the delete's, equality delete file at _strictly less than_ (lines 860-877). Also read at tags 1.6.0, 1.7.0, 1.8.0, 1.9.0, 1.9.1, 1.9.2, 1.10.0, 1.10.1, 1.10.2 to date the "complete and adopted" wording | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/format/spec.md | 2026-05-20 |
| S3 | PR #13175, "Spec: Mark version 3 as completed", merged 2025-05-29, author ajantha-bhat; body cites the mailing-list vote | https://github.com/apache/iceberg/pull/13175 | 2025-05-29 |
| S4 | dev@iceberg.apache.org, "[VOTE] Adopt the v3 spec changes", Ryan Blue, 2025-05-19: lists what v3 includes; "Adoption doesn't change the default table version" | https://www.mail-archive.com/dev@iceberg.apache.org/msg10150.html | 2025-05-19 |
| S5 | dev@iceberg.apache.org, "[RESULT] [VOTE] Adopt the v3 spec changes", Ryan Blue, 2025-05-22: "With 26 +1 votes (11 binding) and no -1 or +0 votes, this passes." | https://www.mail-archive.com/dev@iceberg.apache.org/msg10228.html | 2025-05-22 |
| S6 | `core/src/main/java/org/apache/iceberg/TableMetadata.java`, tag 1.11.0: `DEFAULT_TABLE_FORMAT_VERSION = 2`, `SUPPORTED_TABLE_FORMAT_VERSION = 4`, `MIN_FORMAT_VERSION_ROW_LINEAGE = 3`; `upgradeFormatVersion` "Cannot downgrade v%s table to v%s"; `addSchemaInternal` calls `Schema.checkCompatibility`. Also `TableMetadataParser` writes `next-row-id` for `formatVersion >= 3`. Also the 1.11.0 source tree read locally at the tag for `DeletionVector`, `DeletionVectorStruct`, `io/PartitioningDVWriter`, `puffin/StandardBlobTypes` (`deletion-vector-v1`), `SparkPositionDeltaWrite`, `FlinkParquetReaders`, `BaseParquetReaders`, `ValueReaders`, `ORCSchemaUtil`, and the Flink `DynamicCommitter` position-delete error | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/core/src/main/java/org/apache/iceberg/TableMetadata.java | 2026-05-20 |
| S7 | `TableMetadata.java` at earlier tags: `SUPPORTED_TABLE_FORMAT_VERSION = 2` at 1.5.0 and 1.6.0; `= 3` at 1.7.0, 1.8.0, 1.9.0; `= 4` at 1.10.0 and 1.11.0 | https://github.com/apache/iceberg/blob/apache-iceberg-1.7.0/core/src/main/java/org/apache/iceberg/TableMetadata.java | 2024-11-08 |
| S8 | `site/docs/releases.md`, tag 1.11.0: 1.10.0 release notes (row lineage always on, Spark ADD COLUMN with default unsupported, DV and partition-stats work); 1.8.0 release notes (DV read #11481, DV write #11476, Spark DV for V3 #11561, row lineage metadata #11948); 1.7.0 release notes (Basic Classes for Iceberg Table Version 3 #10760) | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/site/docs/releases.md | 2026-05-20 |
| S9 | Iceberg docs, "Configuration", tag 1.11.0: `format-version` default `2`, "Defaults to 2 since version 1.4.0"; `write.delete.mode` default `copy-on-write`; `write.merge.mode` default `copy-on-write` | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/docs/docs/configuration.md | 2026-05-20 |
| S10 | `api/src/main/java/org/apache/iceberg/Schema.java`, tag 1.11.0: `DEFAULT_VALUES_MIN_FORMAT_VERSION = 3`; `checkCompatibility` rejects non-null `initial-default` below v3 with "non-null default (%s) is not supported until v%s" | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/api/src/main/java/org/apache/iceberg/Schema.java | 2026-05-20 |
| S11 | `core/src/main/java/org/apache/iceberg/SchemaUpdate.java`, tag 1.11.0: `addColumn` / `addRequiredColumn`; `internalAddColumn` sets `withInitialDefault` and `withWriteDefault`; "Incompatible change: cannot add required column without a default value"; `updateColumnDefault` sets only `withWriteDefault`. `api/.../UpdateSchema.java` for the interface | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/core/src/main/java/org/apache/iceberg/SchemaUpdate.java | 2026-05-20 |
| S12 | PR #11481 "Core: Support DVs in DeleteLoader", merged 2024-11-08; PR #11476 "Core, Puffin: Add DV file writer", merged 2024-11-06; PR #11561 "Spark: Write DVs for V3 MoR tables", merged 2024-12-06 | https://github.com/apache/iceberg/pull/11481 | 2024-11-08 |
| S13 | `spark/v4.1/spark/src/main/java/org/apache/iceberg/spark/SparkWriteConf.java` (the module for the pinned Spark 4.1.3; `spark/v4.0` is identical here), tag 1.11.0: `deleteFileFormat()` returns `FileFormat.PUFFIN` when `TableUtil.formatVersion(table) >= 3`; `spark/v4.1/.../source/SparkPositionDeltaWrite.java` selects `PartitioningDVWriter` when `deleteFileFormat == FileFormat.PUFFIN` | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/spark/v4.1/spark/src/main/java/org/apache/iceberg/spark/SparkWriteConf.java | 2026-05-20 |
| S14 | `flink/v2.1/flink/src/main/java/org/apache/iceberg/flink/sink/RowDataTaskWriterFactory.java` (the module for the pinned Flink 2.1.3; `flink/v2.0` is identical here), tag 1.11.0: `this.useDv = TableUtil.formatVersion(table) > 2`; equality writer selected separately by `equalityFieldIds`. `BaseDeltaTaskWriter` uses `PartitioningDVWriter` | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/flink/v2.1/flink/src/main/java/org/apache/iceberg/flink/sink/RowDataTaskWriterFactory.java | 2026-05-20 |
| S15 | PR #11948 "Core, API, Spec: Metadata Row Lineage", merged 2025-02-01, author RussellSpitzer; shipped in 1.8.0 | https://github.com/apache/iceberg/pull/11948 | 2025-02-01 |
| S16 | PR #12986 "REST spec: Remove update to enable row lineage", merged 2025-05-07, author rdblue; release note "remove update to enable row lineage as it is always on for V3 table" | https://github.com/apache/iceberg/pull/12986 | 2025-05-07 |
| S17 | PR #12211 "API, Core: Support default values in UpdateSchema", merged 2025-02-13, author rdblue; shipped in 1.9.0 | https://github.com/apache/iceberg/pull/12211 | 2025-02-13 |
| S18 | PR #13464 "Spark: Throw unsupported for ADD COLUMN with default value", merged 2025-07-07, author amogh-jahagirdar; shipped in 1.10.0 | https://github.com/apache/iceberg/pull/13464 | 2025-07-07 |
| S19 | PR #14407 "Spark 4.0: Add schema conversion support for default values", merged 2025-10-29, author geruh; shipped in 1.11.0 | https://github.com/apache/iceberg/pull/14407 | 2025-10-29 |
| S20 | `spark/v4.1/spark/src/main/java/org/apache/iceberg/spark/TypeToSparkType.java` (pinned Spark 4.1.3; `spark/v4.0` is identical here), tag 1.11.0: `write-default` to `withCurrentDefaultValue`, `initial-default` to `withExistenceDefaultValue` | https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/spark/v4.1/spark/src/main/java/org/apache/iceberg/spark/TypeToSparkType.java | 2026-05-20 |
| S21 | PR #10760 "Core: Adds Basic Classes for Iceberg Table Version 3", merged 2024-08-01, author RussellSpitzer; shipped in 1.7.0 | https://github.com/apache/iceberg/pull/10760 | 2024-08-01 |
| S22 | Internal ADR: `docs/adr/0022-iceberg-format-v2-is-pinned.md` (accepted), v2 pinned because ClickHouse 26.8 LTS cannot read v3 deletion vectors; records `add-required-with-default` as an honest gap | repo file | 2026-09-27 |
| S23 | Internal ADR: `docs/adr/0024-engine-pins-follow-the-iceberg-connector-matrix.md` (accepted), Iceberg 1.11.0 pinned as the current GA release | repo file | 2026-09-27 |
| S24 | PR #11240 "Spec v3: Add deletion vectors to the table spec", merged 2024-11-02, author rdblue; shipped in 1.8.0 | https://github.com/apache/iceberg/pull/11240 | 2024-11-02 |

---

## Verdict

Apache Iceberg format v3 is **final**: adopted by a 26-to-0 community vote on 2025-05-22 [S4], [S5], recorded in the spec by #13175 on 2025-05-29 [S3], and first shipped in the GA release 1.10.0 on 2025-09-11 [S1], [S2]. The Java library accepted the `format-version=3` value earlier, from 1.7.0 on 2024-11-08 [S7], and shipped the substantive v3 features (DVs, row lineage) from 1.8.0 on 2025-02-13 [S8], [S12], [S15]. In the pinned 1.11.0, **native column defaults, deletion vectors and row lineage are all implemented and GA**, with no feature flag other than the opt-in format version (default still 2) and, for DVs, the merge-on-read mode [S9], [S10], [S11], [S12], [S13], [S14], [S15], [S16]. The one real incompleteness is the SQL surface: Spark cannot express `ADD COLUMN ... DEFAULT` and throws, so required-with-default is reachable only through the Iceberg API or via Spark schema conversion [S18], [S19], [S20].

`initial-default` serves pre-existing rows at read time with no file rewrite, and `write-default` fills omitted fields on new writes; a required column can be added with a default in v3 [S2], [S11]. On a v2 table this is impossible by construction: `initial-default` is a v3-only schema attribute and `Schema.checkCompatibility` rejects it below v3 [S10]. The upgrade is a one-way door: `TableMetadata.upgradeFormatVersion` refuses to lower the version [S6], and the spec requires every implementation to throw on a version above its support [S2], so the whole table, not just its v3 features, becomes unreadable to v2-only engines. Finally, v3 does **not** still support v2-style position delete files for new writes: they are forbidden and deprecated, and new deletes must be deletion vectors, with copy-on-write and equality deletes as the only DV-free routes [S2], [S13], [S14].
