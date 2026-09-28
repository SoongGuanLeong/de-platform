# 19 - Does Polaris 1.7.0 serve Iceberg format v3 table metadata?

**Date of research:** 2026-09-28. All evidence accessed 2026-09-28 unless stated.
**Scope:** Apache Polaris 1.7.0 (tag `apache-polaris-1.7.0`, published 2026-08-02) as the Iceberg REST catalog, read against Apache Iceberg 1.11.0 (tag `apache-iceberg-1.11.0`, published 2026-05-20), which is the Iceberg version Polaris 1.7.0 pins. Apache Polaris 1.8.0 (published 2026-09-28) is re-checked where it could differ. Lakekeeper (the documented fallback catalog) is checked at its current release v0.13.6 (2026-09-22).
**Question answered:** Does Polaris 1.7.0 serve Iceberg format v3 table metadata over the Iceberg REST catalog; if not, which Polaris version does and when; does Polaris pass v3 metadata through or must it understand v3 features; does Lakekeeper support v3; and does the Iceberg REST specification itself version-gate the table format?
**Ticket:** [#22 Full Iceberg v3 stack review](https://github.com/SoongGuanLeong/de-platform/issues/22) is issue #22 on map #9. Item 4 of that ticket is "The catalog question. Whether Polaris 1.7.0 serves v3 table metadata. Unverified." This file answers item 4.

---

## Verdict

**Yes. Polaris 1.7.0 serves Iceberg format v3 table metadata, and it has done so since Polaris 1.2.0 (2025-10-28).** The capability is not implemented by Polaris and is not stated by Polaris. It is inherited: Polaris 1.7.0 pins Iceberg 1.11.0 [S2], and Iceberg 1.11.0's `TableMetadata` accepts format versions up to 4 [S10], so v3 passes every check Polaris performs. Polaris has no format-version allowlist of its own, and its vendored REST schema caps `format-version` at 3, which admits v3 and rejects only the unadopted v4 [S8].

**Two corrections to the framing of the ticket.**

1. **Polaris 1.7.0 is no longer the current release.** Apache Polaris 1.8.0 was published on 2026-09-28, the same day as this research, and is not a draft or a prerelease [S1]. Polaris 1.8.0 also pins Iceberg 1.11.0 and keeps the REST cap at 3 [S2][S8], so nothing in this answer changes between 1.7.0 and 1.8.0. Pin 1.8.0 if the platform wants the current release.
2. **This is not a 1.7.0 question.** v3 has been inside the Polaris REST contract since Polaris 1.2.0 (2025-10-28), because that is the first release that shipped a vendored REST schema with `format-version` maximum 3 [S9]. Polaris 1.1.0 shipped a schema capped at 2 [S9].

**Confidence: high on the mechanism, medium on the untested edges.** Every claim below is read from tagged source, not inferred from a blog or a guide. What is *not* established is a live test: no first-party Polaris test creates a v3 table, no Polaris document states v3 support, and the platform has not run a v3 create/load/commit round-trip against a running Polaris. Section 6 states exactly what would falsify the verdict.

---

## 1. The version facts

| Component | Version | Released | Source |
|---|---|---|---|
| Apache Polaris | 1.7.0 | 2026-08-02T05:02:20Z | [S1] |
| Apache Polaris | 1.8.0 | 2026-09-28T04:27:48Z (current; not draft, not prerelease) | [S1] |
| Apache Iceberg | 1.11.0 | 2026-05-20T08:47:57Z | [S15] |
| Lakekeeper | 0.10.0 (first v3 support) | 2025-09-29 | [S18] |
| Lakekeeper | 0.13.0 (format-version policy) | 2026-06-30 | [S18][S24] |
| Lakekeeper | 0.13.6 (current) | 2026-09-22 | [S24] |

The Iceberg format versions themselves are defined by the format specification, not by any catalog. Iceberg 1.11.0's `format/spec.md` states: "Versions 1, 2 and 3 of the Iceberg spec are complete and adopted by the community." It adds, in bold: "Version 4 is under active development and has not been formally adopted." [S13]. Version 3 is defined as adding nanosecond timestamps, `unknown`, `variant`, `geometry`, `geography`; column default values (`initial-default` / `write-default`); multi-argument partition and sort transforms; row lineage (`next-row-id`, `_row_id`, `_last_updated_sequence_number`, `first-row-id`); binary deletion vectors stored as Puffin `deletion-vector-v1` blobs; and table encryption keys [S13].

---

## 2. (1) Does Polaris 1.7.0 support v3 tables via the Iceberg REST catalog, and is there any restriction that rejects v3?

**Verdict: yes, v3 is accepted. There is no Polaris-specific format-version allowlist. The only numeric gates are (a) the Iceberg Java library's supported-version constant and (b) the `maximum` in the vendored OpenAPI schema. v3 is below both.**

The evidence is a five-step chain, all from tagged source.

**2.1 Polaris 1.7.0 pins Iceberg 1.11.0.** `gradle/libs.versions.toml` at tag `apache-polaris-1.7.0` line 23: `iceberg = "1.11.0"` [S2]. Polaris does not vendor a fork of Iceberg's table-metadata model; it uses `org.apache.iceberg.TableMetadata` and `org.apache.iceberg.TableMetadataParser` directly.

**2.2 Iceberg 1.11.0 accepts format versions up to 4.** `core/src/main/java/org/apache/iceberg/TableMetadata.java` at tag `apache-iceberg-1.11.0`, lines 57 to 59:

```
static final int DEFAULT_TABLE_FORMAT_VERSION = 2;
static final int SUPPORTED_TABLE_FORMAT_VERSION = 4;
static final int MIN_FORMAT_VERSION_ROW_LINEAGE = 3;
```

The builder enforces `formatVersion <= SUPPORTED_TABLE_FORMAT_VERSION` at construction (line 308) and on upgrade (line 1048) [S10]. The default is v2, so a table becomes v3 only when the client asks for it, but a request for v3 passes.

**2.3 Polaris's create path reads `format-version` from the request and hands it to Iceberg.** `runtime/service/.../iceberg/IcebergCatalogHandler.java` `stageTableCreateHelper` (lines 628 to 666) builds the property map from the request and calls `TableMetadata.newTableMetadata(schema, spec, sortOrder, location, properties)` [S5]. `TableMetadata.newTableMetadata` reads `TableProperties.FORMAT_VERSION` from those properties (line 73 of `TableMetadata.java`) [S10]. There is no Polaris-side clamp or allowlist between the request and the builder.

**2.4 Polaris's upgrade path is Iceberg's `UpgradeFormatVersion`.** `CatalogHandlerUtils.java` `create` (lines 392 to 405) reads an `UpgradeFormatVersion` update, calls `TableMetadata.buildFromEmpty(formatVersion)`, and applies the rest of the updates [S4]. `IcebergCatalogHandler.java` line 1747 maps `MetadataUpdate.UpgradeFormatVersion` to the authorizable operation `UPGRADE_TABLE_FORMAT_VERSION` [S5]. The value goes straight to Iceberg's builder, which validates it against `SUPPORTED_TABLE_FORMAT_VERSION = 4`.

**2.5 The vendored REST schema admits 1 to 3.** `spec/iceberg-rest-catalog-open-api.yaml` at tag `apache-polaris-1.7.0`, lines 2732 to 2735:

```
format-version:
  type: integer
  minimum: 1
  maximum: 3
```

The same schema is present in Polaris 1.8.0 at lines 2732 to 2735 [S8]. So the REST contract's upper bound is 3, and v3 sits exactly on it.

**What is absent is as important as what is present.** A repository-wide code search over tag `apache-polaris-1.7.0` for `SUPPORTED_TABLE_FORMAT_VERSION` returns zero hits [S16]: Polaris does not re-implement or override Iceberg's constant. Searches for `deletionVector` and `row-lineage` return zero hits [S16]: Polaris has no v3-feature code of its own. There is no Polaris document that states a supported format version, and no Polaris test that creates a v3 table (the `v3` matches in the integration tests are schema-evolution versions, not table format versions).

**Conclusion for (1):** Polaris 1.7.0 accepts and serves v3 table metadata because the Iceberg library it depends on does, and because nothing in Polaris narrows that. The statement is an inference from the dependency and the code path, not a first-party assertion, which is why it is high confidence rather than certain.

---

## 3. (2) Which Polaris version first supported v3, and when?

**v3 first appears in the Polaris REST contract in Polaris 1.2.0 (released 2025-10-28), when Polaris moved from Iceberg 1.9.2 to Iceberg 1.10.0. The library-level capability is older still.**

| Polaris release | Released | Pinned Iceberg | Iceberg Java `SUPPORTED_TABLE_FORMAT_VERSION` | Polaris vendored REST `format-version` max | Source |
|---|---|---|---|---|---|
| 1.1.0-incubating | 2025-09-19 | 1.9.2 | 3 | **2** | [S3][S9][S11] |
| 1.2.0-incubating | 2025-10-28 | 1.10.0 | 4 | **3** | [S3][S9][S10] |
| 1.3.0-incubating | 2026-01-16 | 1.10.0 | 4 | 3 | [S3][S9] |
| 1.4.0 | 2026-04-21 | 1.10.1 | 4 | 3 | [S3][S9] |
| 1.4.1 | 2026-05-01 | 1.10.1 | 4 | 3 | [S3] |
| 1.5.0 | 2026-05-18 | 1.10.1 | 4 | 3 | [S3] |
| 1.6.0 | 2026-07-09 | 1.11.0 | 4 | 3 | [S2][S8] |
| 1.7.0 | 2026-08-02 | 1.11.0 | 4 | 3 | [S2][S8] |
| 1.8.0 | 2026-09-28 | 1.11.0 | 4 | 3 | [S2][S8] |

Two facts in that table need stating plainly.

- **Polaris 1.1.0 could already read a v3 metadata file** because Iceberg 1.9.2's `SUPPORTED_TABLE_FORMAT_VERSION` is 3 [S11]. But its own REST schema advertised maximum 2 [S9], so a v3 response would have violated Polaris 1.1.0's published contract. That is a schema/implementation disagreement, not a capability gap, and it was closed in 1.2.0.
- **The Iceberg REST specification's own cap moved 2 to 3 in Iceberg 1.10.0**, not in 1.11.0 [S15]. Polaris's vendored copy tracks it exactly. So the v3 gate is a property of Iceberg 1.10.0 and later, and every Polaris release from 1.2.0 onward carries it.

**Answer for (2):** the version is 1.2.0, the date is 2025-10-28. 1.7.0 is not the first, and 1.8.0 adds nothing on this axis.

---

## 4. (3) Does Polaris pass v3 metadata through unchanged, or must it understand v3 features?

**Polaris is not a byte-level pass-through. It parses metadata into Iceberg's `TableMetadata` object model and re-serializes it, so it must understand every v3 field it is to preserve. It understands them only to the extent Iceberg 1.11.0 does, because Polaris has no v3 code of its own.**

**4.1 Polaris parses and rewrites, it does not copy bytes.** `LocalIcebergCatalog.java` at tag `apache-polaris-1.7.0`:
- line 434 (`registerTable`) and line 462 (`overwriteRegisteredTable`): `TableMetadata metadata = TableMetadataParser.read(fileIO, metadataFileLocation);` [S6]
- line 2130 (`writeNewMetadata`): `TableMetadataParser.overwrite(metadata, newMetadataLocation);` [S6]
- line 3084: `TableMetadataParser.read(fileIO, newLocation);` [S6]

A raw pass-through would not need the Iceberg object model at all. Polaris reads the metadata JSON, holds it as `TableMetadata`, and writes a new metadata JSON file at a new location on every commit. Anything the Iceberg parser does not recognise is lost on that round-trip.

**4.2 Iceberg 1.11.0's parser does understand the v3 additions that live in table metadata.** `TableMetadataParser.java` at tag `apache-iceberg-1.11.0`:
- write path, line 230: `if (metadata.formatVersion() >= 3) { generator.writeNumberField(NEXT_ROW_ID, metadata.nextRowId()); }` [S12]
- read path, line 477: `if (formatVersion >= 3) { lastRowId = JsonUtil.getLong(NEXT_ROW_ID, node); } else { lastRowId = TableMetadata.INITIAL_ROW_ID; }` [S12]
- encryption keys are written and read unconditionally when present (lines 234 to 240 write, 486 to 492 read) [S12]
- the read guard at lines 343 to 347 rejects only `formatVersion > TableMetadata.SUPPORTED_TABLE_FORMAT_VERSION` [S12]

Row lineage's `_row_id` / `_last_updated_sequence_number` columns live in the schema and in manifests, deletion vectors live in manifests and Puffin files, and default values live in the schema's field metadata [S13]. Those are written by the engine (Spark, Flink) and read by the engine, not assembled by Polaris. Polaris's only job is to preserve the table-metadata JSON, which it does through the Iceberg parser. The platform's own catalogue of v3 write paths is in `docs/research/10-iceberg-write-path-comparison.md`; this file only settles the catalog side.

**4.3 Polaris stores the v3-relevant scalars in its own entity model too.** `polaris-core/.../entity/table/IcebergTableLikeEntity.java` defines `FORMAT_VERSION = "format-version"` (line 58) and `NEXT_ROW_ID = "next-row-id"` (line 85), and `LocalIcebergCatalog.buildTableMetadataPropertiesMap` persists `FORMAT_VERSION` and `NEXT_ROW_ID` from the parsed metadata (lines 2171 and 2182) [S6][S7]. So the row-lineage counter that v3 requires is carried in Polaris's entity state as well as in the metadata file.

**4.4 Polaris is actively adding v3 catalog responsibilities, which confirms it accepts v3 today.** Polaris issue/PR #5185, "[1/2] Enforce immutable Iceberg encryption key IDs" (opened 2026-07-29, open, last updated 2026-09-03), states in its own body: "Polaris already accepts Iceberg table encryption metadata, including when encryption is performed entirely by REST catalog clients." It proposes to reject "Iceberg encryption properties in metadata whose format version is below 3" [S16]. Encryption keys are a v3 feature [S13]. The existence of this open work has two readings, and both are true: Polaris does handle v3 encryption metadata, and catalog-side v3 invariants are still being added rather than finished.

**4.5 What Polaris does not do.** Polaris does not enforce v3 writer rules. It does not assign row IDs, it does not maintain `next-row-id` across snapshots, and it does not merge deletion vectors. Those are writer-engine obligations in the spec [S13]. The catalog enforces authorisation (`TABLE_UPGRADE_FORMAT_VERSION` is a distinct privilege [S5]) and location validation, not v3 data correctness. So "Polaris understands v3" means "Polaris round-trips v3 table metadata", not "Polaris makes a v3 table correct".

**Answer for (3):** Polaris does not pass metadata through untouched; it re-serializes through Iceberg's model, so it must understand v3 fields and does so transitively through Iceberg 1.11.0. It contributes no v3 logic of its own and enforces no v3 writer rules.

---

## 5. (4) Lakekeeper as the fallback catalog: does it support v3 metadata, and which version?

**Verdict: yes, and it is more explicit about v3 than Polaris is. Lakekeeper has supported v3 since 0.10.0 (2025-09-29); since 0.13.0 (2026-06-30) a per-warehouse policy controls which format versions are allowed and which is the default.**

**5.1 The introducing change.** Lakekeeper PR #1364, titled "feat: V3 support", was merged on 2025-09-24 [S17]. The Lakekeeper changelog records "V3 support (#1364)" under release 0.10.0, dated 2025-09-29 [S18]. So the answer to "which version" is 0.10.0, and the date is 2025-09-29.

**5.2 The migration shows what v3 means to Lakekeeper.** `crates/lakekeeper-storage-postgres/migrations/20250923102542_v3_support.sql` (migration timestamp 2025-09-23) [S19]:
- `ALTER TYPE table_format_version ADD VALUE IF NOT EXISTS '3';`
- creates `table_encryption_keys` for v3 table encryption
- adds `next_row_id` to the `table` table, backfilled to 0
- adds snapshot fields `first_row_id`, `assigned_rows` and `key_id`

That is the v3 row-lineage and encryption surface modelled in Lakekeeper's own schema. Polaris keeps the same information only in the metadata file and in a handful of entity properties (section 4.3).

**5.3 Lakekeeper parses `v3` and `3` as create-time values.** `crates/lakekeeper/src/server/tables/create_table.rs` at v0.13.6, lines 434 to 443, maps `"v1" | "1"`, `"v2" | "2"` and `"v3" | "3"` to `FormatVersion::V1/V2/V3` and errors with `InvalidFormatVersion` otherwise [S20]. The same mapping is present at v0.12.0, so this is not a 0.13 novelty.

**5.4 Since 0.13.0 a per-warehouse policy decides what is allowed.** `crates/lakekeeper/src/service/catalog_store/warehouse.rs` defines `AllowedFormatVersions` whose `Default` is `[V1, V2, V3]` (lines 134 to 145) and a `WarehouseFormatVersionPolicy` with `allowed_format_versions` and `default_format_version` [S21]. The migration `20260529120000_warehouse_format_version_policy.sql` adds the columns with `allowed_format_versions smallint[] not null default '{1,2,3}'` [S22]. The 0.13.0 release notes describe it as "Per-warehouse table format-version policy. Set the allowed Iceberg table format versions and an optional default per warehouse, enforced on create/commit/upgrade" [S18]. So a fresh Lakekeeper 0.13.x warehouse allows v3 by default, and an operator can restrict it to v2.

**5.5 Lakekeeper's REST schema caps `format-version` at 3**, matching Iceberg's: `docs/docs/api/rest-catalog-open-api.yaml` lines 2245 to 2248 [S23]. Note there is a second schema in that file with `maximum: 1` (line 2391), which is a view or non-table schema and is not the table metadata schema.

**Answer for (4):** Lakekeeper supports v3 table metadata from 0.10.0 (2025-09-29), stores the v3 row-lineage and encryption fields in its own Postgres schema, and from 0.13.0 exposes a per-warehouse allowed/default format-version policy that defaults to allowing v3. Current release is 0.13.6 (2026-09-22) [S24]. As a fallback for a v3 stack, Lakekeeper is not the weaker option; it is the one whose v3 support is first-party and testable.

---

## 6. (5) Does the Iceberg REST catalog specification itself version-gate the table format?

**Verdict: yes, at the schema level. The REST specification constrains the `format-version` field of the table metadata object to `minimum: 1`, `maximum: 3`. The cap moved from 2 to 3 in Iceberg 1.10.0. The gate is asymmetric: the load/response metadata schema is capped, but the `upgrade-format-version` update is not.**

**6.1 The table metadata schema is capped at 3.** `open-api/rest-catalog-open-api.yaml` at tag `apache-iceberg-1.11.0`, `TableMetadata` schema (declared at line 2721), lines 2727 to 2729: `format-version`, `type: integer`, `minimum: 1`, `maximum: 3` [S14]. Polaris 1.7.0 and 1.8.0 vendor the identical constraint [S8].

**6.2 The cap moved in Iceberg 1.10.0.** The REST schema in Iceberg 1.9.2 has `maximum: 2`; Iceberg 1.10.0 and 1.11.0 have `maximum: 3` [S15]. This is the same release boundary as the Java library's jump from `SUPPORTED_TABLE_FORMAT_VERSION = 3` (Iceberg 1.9.0 and 1.9.2) to `= 4` (Iceberg 1.10.0 onward) [S11][S10].

**6.3 `CreateTableRequest` has no `format-version` field.** The schema (line 3746) carries `name`, `location`, `schema`, `partition-spec`, `write-order`, `stage-create` and a free-form `properties` map [S14]. The format version therefore travels as a property, which is why Polaris's create path reads it out of `properties` in section 2.3 rather than from a dedicated field.

**6.4 `UpgradeFormatVersionUpdate.format-version` is an unbounded integer.** The schema (line 2952) declares `format-version: type: integer` with no `minimum` and no `maximum` [S14]. So the REST specification caps the format version that may appear in returned metadata, but does not cap the value a client may ask to upgrade to. The only ceiling on an upgrade is the server's implementation.

**6.5 The schema cap (3) and the Java library cap (4) disagree, and Polaris follows the library.** Iceberg 1.11.0's Java accepts up to 4 [S10] while its own REST schema caps at 3 [S14]. Iceberg resolves this by declaring v4 unadopted [S13]: the library reads forward, the wire contract does not promise it. Polaris, which has no independent check (section 2), would therefore accept a `format-version=4` request if one were sent as a create property, and would then return metadata that violates its own vendored `maximum: 3`. This is an observation from reading the two sources together, not a measured behaviour; it is recorded because it is the one place the gates can be made to disagree, and because it is trivially testable (section 7).

**Answer for (5):** the specification does version-gate the table format, at `maximum: 3` for metadata from Iceberg 1.10.0 onward, and it does not gate the upgrade request. A catalog is therefore free by the letter of the spec to accept an upgrade to a version its own response schema cannot represent, which is exactly the disagreement that exists in Iceberg 1.11.0 and is inherited by Polaris 1.7.0.

---

## 7. What would falsify this

The verdict is an inference from tagged source. These are the checks that would turn it into a measurement, in order of value.

1. **Create a v3 table through a running Polaris 1.7.0 and load it back.** Send a `CreateTableRequest` whose properties include `format-version=3`, then `loadTable` and assert the returned `metadata.format-version` is 3 and that `next-row-id` is present. This is the single test that confirms section 2 end to end.
2. **Round-trip a v3 feature through the catalog.** Write a v3 table with a column `initial-default`, commit it through Polaris, load it, and assert the default survives. Then write one with a deletion vector and assert the manifest-level reference survives. This tests the section 4 claim that the re-serialization is lossless for v3 fields.
3. **Send `format-version=4` and observe.** If Polaris rejects it with a 400, the vendored `maximum: 3` is enforced by the generated REST layer and section 6.5 is wrong. If Polaris accepts it and returns `format-version: 4`, section 6.5 is confirmed and the platform should not rely on the REST cap as a guard.
4. **Register an externally written v3 metadata file.** Use `registerTable` against a metadata JSON produced by Spark 4.x at v3, and assert Polaris accepts it and preserves `next-row-id` and encryption keys.

Until at least check 1 is run, the correct status is "supported by construction, not yet measured on this platform".

---

## 8. Could not verify

- **Any first-party Polaris statement that v3 is supported.** Polaris documents no supported format version, and a code search finds no v3-specific code or test [S16]. The verdict rests on the dependency and the absence of a restriction, which is a strong inference but not a vendor promise.
- **Whether the generated Polaris REST layer enforces the OpenAPI `maximum: 3`.** The schema carries the constraint; whether Quarkus or the OpenAPI generator enforces it at runtime was not tested. This is the same gap as section 6.5.
- **Whether Polaris 1.2.0 through 1.6.0 accepted v3 end to end.** Their pins and vendored schemas were read [S3][S9], but the create and commit code paths were only read at 1.7.0. The table in section 3 is therefore exact on versions and dates and inferred on runtime behaviour for the pre-1.7 releases.
- **Whether Polaris 1.8.0 changes v3 behaviour beyond the version pins.** 1.8.0's Iceberg pin and REST cap were read and are unchanged [S2][S8], and its release notes contain no format-version item. A full source diff between 1.7.0 and 1.8.0 was not performed.
- **Lakekeeper's v3 behaviour at runtime.** Its v3 support is read from the migration, the create-table parser, the warehouse policy and the changelog [S17][S18][S19][S20][S21][S22]. No Lakekeeper instance was run, and whether its Rust `iceberg` dependency round-trips every v3 field the way Iceberg 1.11.0 does was not tested.
- **The Iceberg Rust crate's exact v3 coverage.** Lakekeeper pins `iceberg` to a git revision of `lakekeeper/iceberg-rust` [S25]. The crate's `FormatVersion::V3` variant exists and is accepted, but the completeness of its v3 metadata support was not audited.

---

## Sources

All accessed 2026-09-28 unless a different date is stated.

- [S1] Apache Polaris releases, GitHub REST API. `repos/apache/polaris/releases`. Confirms `apache-polaris-1.7.0` published 2026-08-02T05:02:20Z and `apache-polaris-1.8.0` published 2026-09-28T04:27:48Z with `draft: false`, `prerelease: false`. https://github.com/apache/polaris/releases
- [S2] Apache Polaris `gradle/libs.versions.toml`, line 23 `iceberg = "1.11.0"`, at tags `apache-polaris-1.6.0`, `apache-polaris-1.7.0` and `apache-polaris-1.8.0`. https://github.com/apache/polaris/blob/apache-polaris-1.7.0/gradle/libs.versions.toml
- [S3] Apache Polaris `gradle/libs.versions.toml` across older tags: `apache-polaris-1.1.0-incubating` pins `iceberg = "1.9.2"`; `1.2.0-incubating` and `1.3.0-incubating` pin `"1.10.0"`; `1.4.0`, `1.4.1` and `1.5.0` pin `"1.10.1"`.
- [S4] Apache Polaris `runtime/service/src/main/java/org/apache/polaris/service/catalog/iceberg/CatalogHandlerUtils.java`, tag `apache-polaris-1.7.0`, `create` at lines 392 to 405 (`UpgradeFormatVersion`, `TableMetadata.buildFromEmpty`). https://github.com/apache/polaris/blob/apache-polaris-1.7.0/runtime/service/src/main/java/org/apache/polaris/service/catalog/iceberg/CatalogHandlerUtils.java
- [S5] Apache Polaris `runtime/service/src/main/java/org/apache/polaris/service/catalog/iceberg/IcebergCatalogHandler.java`, tag `apache-polaris-1.7.0`. `stageTableCreateHelper` lines 628 to 666 (property map and `TableMetadata.newTableMetadata`); `UPGRADE_TABLE_FORMAT_VERSION` mapping at line 1747. https://github.com/apache/polaris/blob/apache-polaris-1.7.0/runtime/service/src/main/java/org/apache/polaris/service/catalog/iceberg/IcebergCatalogHandler.java
- [S6] Apache Polaris `runtime/service/src/main/java/org/apache/polaris/service/catalog/iceberg/LocalIcebergCatalog.java`, tag `apache-polaris-1.7.0`. `TableMetadataParser.read` at lines 434, 462 and 3084; `TableMetadataParser.overwrite` at line 2130; `FORMAT_VERSION` and `NEXT_ROW_ID` persisted at lines 2171 and 2182. https://github.com/apache/polaris/blob/apache-polaris-1.7.0/runtime/service/src/main/java/org/apache/polaris/service/catalog/iceberg/LocalIcebergCatalog.java
- [S7] Apache Polaris `polaris-core/src/main/java/org/apache/polaris/core/entity/table/IcebergTableLikeEntity.java`, tag `apache-polaris-1.7.0`, `FORMAT_VERSION` at line 58 and `NEXT_ROW_ID` at line 85, both documented as copied from Iceberg's `TableMetadataParser`.
- [S8] Apache Polaris `spec/iceberg-rest-catalog-open-api.yaml`, tags `apache-polaris-1.7.0` and `apache-polaris-1.8.0`, `TableMetadata` schema at line 2731 with `format-version` `minimum: 1`, `maximum: 3` at lines 2732 to 2735. https://github.com/apache/polaris/blob/apache-polaris-1.7.0/spec/iceberg-rest-catalog-open-api.yaml
- [S9] Apache Polaris `spec/iceberg-rest-catalog-open-api.yaml` across tags: `apache-polaris-1.1.0-incubating` has `minimum: 1`, `maximum: 2`; `1.2.0-incubating`, `1.3.0-incubating`, `1.4.0` and `1.6.0` have `minimum: 1`, `maximum: 3`.
- [S10] Apache Iceberg `core/src/main/java/org/apache/iceberg/TableMetadata.java`, tag `apache-iceberg-1.11.0`: `DEFAULT_TABLE_FORMAT_VERSION = 2` line 57, `SUPPORTED_TABLE_FORMAT_VERSION = 4` line 58, `MIN_FORMAT_VERSION_ROW_LINEAGE = 3` line 59; `formatVersion <= SUPPORTED_TABLE_FORMAT_VERSION` checks at lines 308 and 1048; `format-version` read from properties at line 73. The same constants are present at tag `apache-iceberg-1.10.0`. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/core/src/main/java/org/apache/iceberg/TableMetadata.java
- [S11] Apache Iceberg `core/src/main/java/org/apache/iceberg/TableMetadata.java` at tags `apache-iceberg-1.9.0` and `apache-iceberg-1.9.2`: `SUPPORTED_TABLE_FORMAT_VERSION = 3`.
- [S12] Apache Iceberg `core/src/main/java/org/apache/iceberg/TableMetadataParser.java`, tag `apache-iceberg-1.11.0`: version guard at lines 343 to 347; v3 `next-row-id` write at line 230 and read at line 477; encryption keys write at lines 234 to 240 and read at lines 486 to 492. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/core/src/main/java/org/apache/iceberg/TableMetadataParser.java
- [S13] Apache Iceberg `format/spec.md`, tag `apache-iceberg-1.11.0`: "Versions 1, 2 and 3 of the Iceberg spec are complete and adopted by the community" and "Version 4 is under active development and has not been formally adopted" at lines 27 and 29; v3 feature list at lines 47 to 58; "Version 3" appendix at line 1650; row lineage at lines 398 to 481; deletion vectors at lines 1115 to 1152; default values at lines 262 to 286. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/format/spec.md
- [S14] Apache Iceberg `open-api/rest-catalog-open-api.yaml`, tag `apache-iceberg-1.11.0`: `TableMetadata` at line 2721 with `format-version` `minimum: 1`, `maximum: 3` at lines 2727 to 2729; `CreateTableRequest` at line 3746; `UpgradeFormatVersionUpdate` at line 2952 with an unbounded `format-version` integer. https://github.com/apache/iceberg/blob/apache-iceberg-1.11.0/open-api/rest-catalog-open-api.yaml
- [S15] Apache Iceberg releases and REST schema caps: releases API gives `apache-iceberg-1.11.0` published 2026-05-20T08:47:57Z; the `TableMetadata` `format-version` cap is `maximum: 2` at tag `apache-iceberg-1.9.2` and `maximum: 3` at tags `apache-iceberg-1.10.0` and `apache-iceberg-1.11.0`. https://github.com/apache/iceberg/releases
- [S16] Apache Polaris repository searches at tag `apache-polaris-1.7.0`, GitHub code search: `SUPPORTED_TABLE_FORMAT_VERSION` 0 hits; `deletionVector` 0 hits; `row-lineage` 0 hits; `format version` only in the Python CLI and Ranger service definition. Issue/PR #5185 "[1/2] Enforce immutable Iceberg encryption key IDs", opened 2026-07-29, state open, updated 2026-09-03; body states "Polaris already accepts Iceberg table encryption metadata" and proposes rejecting encryption properties below format version 3. https://github.com/apache/polaris/pull/5185
- [S17] Lakekeeper PR #1364 "feat: V3 support", merged 2025-09-24T16:52:30Z, base `main`. https://github.com/lakekeeper/lakekeeper/pull/1364
- [S18] Lakekeeper changelog and release notes at tag `v0.13.6`: `crates/lakekeeper/CHANGELOG.md` lists "V3 support (#1364)" under `## [0.10.0] (2025-09-29)`; `site/docs/about/release-notes.md` lists the per-warehouse format-version policy under v0.13.0 (2026-06-30) as "Set the allowed Iceberg table format versions and an optional default per warehouse, enforced on create/commit/upgrade (#1786)". https://github.com/lakekeeper/lakekeeper/blob/v0.13.6/crates/lakekeeper/CHANGELOG.md
- [S19] Lakekeeper `crates/lakekeeper-storage-postgres/migrations/20250923102542_v3_support.sql`, tag `v0.13.6`: adds `'3'` to `table_format_version`, creates `table_encryption_keys`, adds `next_row_id` to `table`, and adds snapshot columns `first_row_id`, `assigned_rows` and `key_id`.
- [S20] Lakekeeper `crates/lakekeeper/src/server/tables/create_table.rs`, tag `v0.13.6`, lines 434 to 443 map `"v3" | "3"` to `FormatVersion::V3`; the same mapping is present at tag `v0.12.0`. https://github.com/lakekeeper/lakekeeper/blob/v0.13.6/crates/lakekeeper/src/server/tables/create_table.rs
- [S21] Lakekeeper `crates/lakekeeper/src/service/catalog_store/warehouse.rs`, tag `v0.13.6`: `AllowedFormatVersions` default of `V1, V2, V3` at lines 134 to 145; `WarehouseFormatVersionPolicy` at line 222. https://github.com/lakekeeper/lakekeeper/blob/v0.13.6/crates/lakekeeper/src/service/catalog_store/warehouse.rs
- [S22] Lakekeeper `crates/lakekeeper-storage-postgres/migrations/20260529120000_warehouse_format_version_policy.sql`, tag `v0.13.6`: `allowed_format_versions smallint[] not null default '{1,2,3}'` and `default_format_version smallint`, with constraints. Present at tag `v0.13.0`.
- [S23] Lakekeeper `docs/docs/api/rest-catalog-open-api.yaml`, tag `v0.13.6`, `format-version` `minimum: 1`, `maximum: 3` at lines 2245 to 2248. https://github.com/lakekeeper/lakekeeper/blob/v0.13.6/docs/docs/api/rest-catalog-open-api.yaml
- [S24] Lakekeeper releases, GitHub REST API: `v0.13.6` published 2026-09-22T09:27:40Z. https://github.com/lakekeeper/lakekeeper/releases
- [S25] Lakekeeper `Cargo.toml`, tag `v0.13.6`, pins `iceberg = { git = "https://github.com/lakekeeper/iceberg-rust.git", rev = "2056f3e4d53129039f2229f3b326aa538289be27" }`.
