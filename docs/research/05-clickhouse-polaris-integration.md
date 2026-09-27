# 05 - ClickHouse and Apache Polaris: native integration status

**Date of research:** 2026-09-27. All evidence accessed 2026-09-27 unless stated.
**Scope:** ClickHouse's own documentation, source code, and first-party blog, screened for any native or first-party integration with Apache Polaris or with an Iceberg REST catalog. Version read: ClickHouse `master` as of 2026-09-27, cross-checked against the latest stable release `v26.9.3.38-stable` (published 2026-09-26) and the current LTS line 26.8 (`v26.8.12.53-lts`). Apache Polaris 1.1.0 is the version ClickHouse's own Polaris guide links to.
**Question answered:** Does ClickHouse have any native or first-party integration with Apache Polaris, or with an Iceberg REST catalog generally, and what exactly does it do.

---

## 1. The direct answer

Yes, but it is not a Polaris-specific connector. ClickHouse's Polaris support is delivered as generic **Iceberg REST catalog** support inside the `DataLakeCatalog` database engine, with `catalog_type = 'rest'`. ClickHouse additionally ships a dedicated first-party Polaris guide. The integration speaks the Iceberg REST catalog protocol. It is **Beta**, not GA. Through the catalog it is **read-only**: ClickHouse discovers tables, reads their schema and metadata, optionally obtains vended storage credentials, and then reads the data files directly from object storage. The catalog never carries table data.

## 2. (a) Does ClickHouse's Iceberg support speak the Iceberg REST catalog protocol?

Yes. This is a first-party implementation, not a bridge.

- What the documentation states: the `DataLakeCatalog` database engine lists **"REST Catalogs - Any catalog supporting the Iceberg REST specification"** as a supported catalog, with `catalog_type = 'rest' (Iceberg)` [S3]. The REST catalog guide states: "ClickHouse supports integration with multiple catalogs (Unity, Glue, REST, Polaris, etc.)" and links the Iceberg REST OpenAPI specification [S2]. The Data Lakes overview says the "Iceberg REST Catalog can be used with Iceberg tables" [S6].
- What the source code does: the REST client is `RestCatalog` in `src/Databases/DataLake/RestCatalog.cpp` / `.h`. It builds URLs of the form `/v1/{prefix}/namespaces/{namespace}/tables/{table}`, reads the catalog config from `/v1/config`, follows the `next-page-token` continuation token defined by the Iceberg REST OpenAPI spec, and requests vended credentials with the header `X-Iceberg-Access-Delegation: vended-credentials` [S12]. The accepted `catalog_type` string `"rest"` maps to the internal enum `DatabaseDataLakeCatalogType::ICEBERG_REST` [S11].
- Feature name: the `DataLakeCatalog` **database engine** with `catalog_type = 'rest'`. Do not look for a separate "Polaris connector"; there is none.
- Version and stability:
  - The Iceberg REST catalog path was introduced in **24.12** under the setting `allow_experimental_database_iceberg`. In **25.8** that setting was renamed to `allow_database_iceberg`, keeping the old name as an alias. This is recorded in the setting's own version history in `src/Core/Settings.cpp` [S10]. The official ClickHouse Inc blog confirms the timeline: catalog support began in 24.12 with Unity Catalog, and "The Polaris catalog was supported as well", with Iceberg REST Catalog support added afterwards [S16].
  - The setting is currently declared with the **BETA** flag in source [S10]. The source throws, verbatim: "DatabaseDataLake with Iceberg Rest catalog is beta. To allow its usage, enable setting allow_database_iceberg" [S14]. The docs carry a Beta badge [S2].
  - The dedicated Polaris guide states it requires **ClickHouse version 26.1+** [S1].
  - So: **GA, no. Experimental originally, Beta now.** The exact status depends on which minor you pin.
- Documentation inconsistency to be aware of: the Polaris guide's own note says "As this feature is experimental, you will need to enable it using: `SET allow_experimental_database_unity_catalog = 1;`" [S1]. That note is wrong on both counts. The REST catalog guide says beta with `allow_database_iceberg` [S2], and the source declares `allow_database_iceberg` as BETA with `allow_experimental_database_unity_catalog` only an alias for the Unity path [S10]. Use `SET allow_database_iceberg = 1;`. This looks like a copy-paste error in the Polaris guide.

## 3. (b) First-party ClickHouse material on Polaris and REST catalogs

There is first-party documentation. There is no dedicated ClickHouse Inc engineering blog post about Polaris specifically.

- **A dedicated Polaris guide exists**: "Polaris catalog", slug `/use-cases/data-lake/polaris-catalog`, source `docs/use-cases/data_lake/reference/polaris.md` in `ClickHouse/clickhouse-docs`, last content commit 2026-03-31 [S1]. It is a first-party ClickHouse doc that walks through connecting to Apache Polaris (self-hosted) or Snowflake Open Catalog (hosted Polaris), and shows the working `CREATE DATABASE` form:
  ```sql
  CREATE DATABASE polaris_catalog
  ENGINE = DataLakeCatalog('https://<catalog_uri>/api/catalog/v1')
  SETTINGS
      catalog_type = 'rest',
      catalog_credential = '<client-id>:<client-secret>',
      warehouse = 'snowflake',
      auth_scope = 'PRINCIPAL_ROLE:ALL',
      oauth_server_uri = 'https://<catalog_uri>/api/catalog/v1/oauth/tokens',
      storage_endpoint = '<storage_endpoint>'
  ```
  It notes "Apache Polaris supports Iceberg tables and Delta Tables (via Generic Tables). This integration only supports Iceberg tables at this time" [S1].
- **A generic REST catalog guide exists**: "REST catalog", slug `/use-cases/data-lake/rest-catalog` [S2].
- **A first-party blog post mentions Polaris**: "ClickHouse is data lake ready", ClickHouse Inc, 2026-08-31, states that in 24.12 ClickHouse introduced catalog support with Unity Catalog and that "The Polaris catalog was supported as well" [S16]. It is a general data lake announcement, not a Polaris engineering deep-dive.
- **What does not exist**: no ClickHouse Inc engineering blog post dedicated to Polaris; no separate Polaris client library, driver, or plugin; no Polaris-specific code path in the source tree (Polaris is exercised through the generic `RestCatalog`). The only Polaris-specific artefacts found in source and changelog are bug fixes to the generic REST path that happen to cite Polaris, for example an Azure path fix "Fix polaris catalog with azure" in the 26.4 changelog [S21].

## 4. (c) What ClickHouse offers for Iceberg today, by exact name

All names below are as ClickHouse writes them. Sources: [S4] (engine), [S5] (table function), [S3] (DataLakeCatalog), [S10] (settings and version history), [S7] (support matrix).

### Table functions
- `iceberg` (documented alias of `icebergS3`)
- `icebergS3`, `icebergAzure`, `icebergHDFS`, `icebergLocal`
- Distributed variants: `icebergCluster`, `icebergS3Cluster`, `icebergAzureCluster`

### Table engines
- `IcebergS3`, `IcebergAzure`, `IcebergHDFS`, `IcebergLocal`
- `Iceberg` (auto-detects the backend from the `disk` setting and dispatches to `IcebergS3`, `IcebergAzure`, or `IcebergLocal`; defaults to `IcebergS3` when no disk is set)

### Catalog-aware object
- `DataLakeCatalog` **database engine**: `CREATE DATABASE ... ENGINE = DataLakeCatalog(catalog_endpoint[, user, password]) SETTINGS catalog_type = ...`. Accepted `catalog_type` values, from source: `rest`, `unity`, `glue`, `hive`, `onelake`, `biglake`, `paimon_rest`, `horizon`, `s3tables`, `delta_sharing` [S11]. Note the setting description in `Settings.cpp` says `catalog_type = 'iceberg'` [S10], but the actual accepted string is `'rest'`; the description is imprecise.
- Relevant `DataLakeCatalog` settings: `catalog_type`, `warehouse`, `catalog_credential`, `auth_header`, `auth_scope` (default `PRINCIPAL_ROLE:ALL`), `oauth_server_uri`, `oauth_server_use_request_body`, `storage_endpoint`, `storage_uri_style`, `vended_credentials` (default `true`), `force_add_bucket` (default `false`), plus AWS/Azure/Google credential settings [S3][S15].
- `force_add_bucket` is explicitly a Polaris accommodation. Its own description reads: "Set to `true` for catalogs that hand back paths without the bucket and require it to be added at the URL-construction step (Polaris-style paths)" [S3][S15].

### Feature-flag settings for catalogs
- `allow_database_iceberg` (BETA; the Iceberg REST path; new in 24.12 as `allow_experimental_database_iceberg`, alias added 25.8)
- `allow_database_unity_catalog` (BETA), `allow_database_glue_catalog` (BETA)
- `allow_experimental_database_hms_catalog`, `allow_experimental_database_paimon_rest_catalog`

### Metadata caching
- `use_iceberg_metadata_files_cache` (since 25.4, default `1`): in-memory cache of manifest files, manifest lists, and metadata JSON [S4][S8].
- `iceberg_metadata_staleness_ms` (since 26.3, default `0`): a query setting that accepts cached metadata when fresher than the window, skipping the per-query catalog round trip [S8][S4].
- `iceberg_metadata_async_prefetch_period_ms` (default `0`, disabled): background prefetch of the latest metadata snapshot; runs on `iceberg_background_schedule_pool_size` (server config, default 10) [S4].
- `iceberg_metadata_file_path`, `iceberg_metadata_table_uuid`, `iceberg_recent_metadata_file_by_last_updated_ms_field`: pin metadata resolution when multiple metadata files exist [S8][S5].
- System tables: `system.iceberg_files`, `system.iceberg_history` (25.6), `system.iceberg_metadata_log` [S4][S8].

### Data caching
- No Iceberg-specific data cache object. `Iceberg` engine and table function use the same data cache as `S3`, `AzureBlobStorage`, and `HDFS`, controlled by `enable_filesystem_cache`, which keeps hot Parquet files on local disk between queries [S4][S8].

### Query and write settings
- Read/pruning: `use_iceberg_partition_pruning` (new 25.1, default `1` since 25.6), `use_iceberg_manifest_list_partition_pruning` (26.9, default `1`), `iceberg_tolerate_conflicting_manifest_schemas`.
- Time travel: `iceberg_timestamp_ms`, `iceberg_snapshot_id` (both 25.4) [S8].
- Writes: `allow_insert_into_iceberg` (new 25.7, moved to Beta in 26.2), `iceberg_insert_max_rows_in_data_file` (25.9), `iceberg_insert_max_bytes_in_data_file` (25.9), `iceberg_insert_max_partitions` (25.12), `allow_experimental_iceberg_compaction` (25.8), `iceberg_manifest_min_count_to_compact` (26.7, default 100 since 26.9), `allow_iceberg_remove_orphan_files`, `allow_experimental_cleanup_old_data_files_compaction` (26.5), `allow_experimental_expire_snapshots`, `iceberg_use_version_hint`, `iceberg_metadata_compression_method` [S10][S8].

## 5. (d) Does the catalog ever carry data bytes?

No. The two-layer picture holds. The catalog authorises and describes; the engine fetches bytes directly from object storage.

Evidence from source:
- The catalog interface returns a `TableMetadata` object carrying the table **location**, **schema**, and optionally **storage credentials** (`withLocation()`, `withSchema()`, `withStorageCredentials()`, `withForceAddBucket()`) [S13]. There is no interface for reading data rows through the catalog.
- `RestCatalog` reads the table's `metadata-location` from the REST `loadTable` response and requests vended credentials via `X-Iceberg-Access-Delegation: vended-credentials` [S12]. The catalog returns S3 keys or Azure SAS tokens; it does not stream Parquet.
- Note on source of truth: the ClickHouse Polaris guide itself does not mention `X-Iceberg-Access-Delegation` or `vended_credentials` at all, and leaves the credential question to `storage_endpoint` [S1]. The vending behaviour above is therefore **source-verified, not guide-verified**. Treat the guide as a configuration example, not as documentation of the credential path.
- `DatabaseDataLake` takes the catalog-provided location and constructs a `StorageObjectStorage` / `StorageObjectStorageCluster` over it, applying vended or static storage credentials [S14]. That storage engine is the same object-storage reader used by `S3` and `AzureBlobStorage` tables. Data bytes flow from object storage to ClickHouse, not through the catalog.
- The docs describe the design as querying "without the need for data duplication" and state "Data is never duplicated in ClickHouse" [S3][S8].

What still sits on the catalog path:
- Metadata resolution and table discovery do hit the catalog. The docs are explicit: "Catalog-connected Iceberg tables pay a metadata fetch on each query unless you cache it" [S8]. This is why `iceberg_metadata_staleness_ms` and async prefetch exist. So the catalog remains on the **metadata** path and can deny access, which is the authorisation half of the two-layer model.
- Credential vending is optional: `vended_credentials` defaults to `true`, but if disabled you supply static credentials [S3][S15].

Inference (labelled as such): because data reads use the generic object-storage reader, ClickHouse's Iceberg path cannot enforce catalog-side row filters, column masks, or fine-grained access controls on the data itself. Any such enforcement is a property of the catalog only insofar as it can withhold metadata or credentials. I found no documentation claiming ClickHouse routes data reads through the catalog, and the source is consistent with it not doing so.

## 6. (e) Documented limitations

Read-only through a catalog:
- The support matrix is unambiguous: for **Iceberg REST**, Read is "Beta", **Create table is no, INSERT is no** [S7]. It then states: "With the exception of Microsoft OneLake, Databricks Unity Catalog, and SeaweedFS, all catalogs expose **read-only** access - tables can be queried but not created or written to through the catalog connection." Polaris is not in the exception list, so a Polaris-backed `DataLakeCatalog` table is read-only [S7].
- Writes to Iceberg exist, but only for standalone Iceberg tables on writable storage (the `IcebergS3` / `IcebergLocal` engines and the `iceberg` table function), since 25.7, Beta from 26.2, gated by `allow_insert_into_iceberg` [S5][S7]. The recommended pattern to get MergeTree performance is `INSERT INTO <MergeTree table> SELECT * FROM catalog.table` [S1][S9].

Not MergeTree, and no MergeTree features:
- Iceberg tables are not MergeTree tables. They have no primary key, no `ORDER BY`, no parts, no merges, no TTL, no mutations, and no MergeTree projections or skip indices. The docs frame the whole point of loading into MergeTree as gaining those features: skip indices, full-text indices, and storage "optimized for concurrent reads" that "open table formats are not designed for" [S9].
- Projections specifically: the documentation does not describe projections for Iceberg reads. Inference: because projections are a MergeTree-family feature and catalog-backed Iceberg tables are not MergeTree, they are not available. I did not find a doc sentence stating this negatively, so treat it as an inference rather than a documented limitation.

Predicate pushdown and pruning:
- Partition pruning is on by default: `use_iceberg_partition_pruning` is `1` since 25.6 [S10][S8]. You must filter on the Iceberg **source column** for hidden partitioning to prune [S8].
- Manifest-list partition pruning was added in 26.9 (`use_iceberg_manifest_list_partition_pruning`) [S10].
- `PREWHERE` is supported on Iceberg and other lake reads from 26.2, filtering at the Parquet layer before reading remaining columns [S8].
- Column pruning is inherent: ClickHouse reads Parquet column-by-column from object storage, so `SELECT` narrower columns reduce bytes [S8].
- Merge-on-read tables with heavy position or equality deletes apply filtering during scans, so expect more work per file [S8].
- Catalog listing pushdown: since 26.7, `SHOW TABLES` and `system.tables` push namespace-bound predicates to the catalog to avoid a full catalog scan [S21].

Other documented limitations:
- `ALTER TABLE ... DROP PARTITION` is "currently supported for local and object-storage Iceberg tables, but **not for catalog-backed tables**" [S4]. So a Polaris-backed table cannot use it.
- Format versions: v1 and v2 supported; **v3 is partial**. Deletion vector reads are supported, but manifest compaction is not [S5]. Deletion vector support is read-only; ClickHouse does not write, update, or compact deletion vectors, and `ALTER TABLE ... DELETE` / `UPDATE` are not supported on v3 tables [S5].
- Schema evolution is supported for reads (add, remove, reorder, required to nullable, and a few casts: int to long, float to double, decimal widening), but nested structures and array/map element types cannot change [S4].
- Write-side schema restrictions: ClickHouse cannot create or evolve an Iceberg schema containing `Bool`, `Decimal`, `FixedString`, `Int8`, `UInt8`, `Int16`, or `UInt16`, and maps every `DateTime`/`DateTime64` to Iceberg `timestamp` (microseconds, no timezone) [S4].
- Namespace handling: "Backticks are required because ClickHouse doesn't support more than one namespace", so a catalog table is addressed as `database_name.`schema.table`` [S1][S2].
- Performance caveat, with a number from ClickHouse's own guide: on a ~283 million row Parquet Iceberg dataset, the direct scan took "nearly **9 seconds**" as a full table scan; loading into MergeTree then querying "improves performance dramatically" [S9]. Treat this as an illustrative first-party benchmark, not a controlled one.

## 7. What this means for de-platform

- Polaris over SeaweedFS is a viable read path for ClickHouse today: `DataLakeCatalog` with `catalog_type = 'rest'`, `oauth_server_uri`, `auth_scope`, and `storage_endpoint`, on ClickHouse 26.1+ (Beta). Because Polaris returns bucket-less paths, expect to need `force_add_bucket = true` [S3].
- Credential vending on a no-STS backend, and whether ClickHouse falls back gracefully. Polaris 1.7.0 only mints a prefix-scoped credential when the storage integration implements STS. On a no-STS store the config carries `stsUnavailable: true`, `AssumeRole` is skipped, and no credential is vended; Polaris's own storage docs say the client "must omit `X-Iceberg-Access-Delegation: vended-credentials` and authenticate to the object store directly", and if a client still requests vending Polaris throws `IllegalArgumentException` rather than returning an empty credential set. That Polaris-side behaviour is a cross-reference to `docs/research/04-polaris-authorisation-model.md` [S22], not independently verified here.
  I did verify the ClickHouse side directly, at tag `v26.9.3.38-stable`. The header is **not** sent unconditionally on the read path. `RestCatalog::getTableMetadataImpl` adds `X-Iceberg-Access-Delegation: vended-credentials` only `if (result.requiresCredentials())` (`RestCatalog.cpp` line 1691-1693). `requiresCredentials()` returns the `with_storage_credentials` flag (`ICatalog.h` line 92), and that flag is set only when the `vended_credentials` setting is true (`DatabaseDataLake.cpp` line 736-738). The credential-refresh callback is likewise not registered when vending is off (`DatabaseDataLake.cpp` line 933-936) [S12][S13][S14].
  Consequence: with the **default** `vended_credentials = true`, ClickHouse sends the header on `loadTable` and a no-STS Polaris backend is expected to fail, so the failure is real out of the box. With `vended_credentials = false`, ClickHouse omits the header on the read path and does not register the refresh callback, so the fallback to static credentials (`aws_access_key_id` / `aws_secret_access_key`, or credentials supplied with `storage_endpoint`) is graceful on reads, not a hard fail. The header is sent unconditionally only in `RestCatalog::sendRequest`, which serves catalog DDL and mutation calls (`createNamespaceIfNotExists`, `createTable`, `updateMetadata`, `updateSchema`, `dropTable`), and in the refresh callback; neither is reached on the read path when vending is off, and catalog writes are not supported over REST anyway [S12]. Test recommendation: assert both directions, that the default reproduces the Polaris error, and that `vended_credentials = false` with static credentials reads successfully. SeaweedFS is not assumed STS-less: SeaweedFS 4.47 ships an STS implementation, so the open question is interop, namely whether Polaris's AWS SDK STS client can call SeaweedFS's STS endpoint and whether SeaweedFS honours the inline session policy Polaris sends. Report 04 now states this and gives concrete pass/fail assertions for that test, including the decisive one, that a credential vended for table A must be denied on table B's prefix; see `docs/research/04-polaris-authorisation-model.md` [S22]. Polaris's documented non-STS examples are Ozone S3 gateway and Ceph RGW. Pin both the Polaris version (the ClickHouse guide is written against Polaris 1.1.0, six minors behind the 1.7.0 the teammate read) and the ClickHouse version.
- ClickHouse will **not** write through Polaris. The serving-layer pattern is: query the catalog table, then `INSERT INTO SELECT` into a native MergeTree table for fast, high-concurrency serving. That matches the ClickHouse-documented pattern [S1][S9].
- The catalog remains on the metadata path per query. Plan to set `iceberg_metadata_staleness_ms` and, where useful, `iceberg_metadata_async_prefetch_period_ms` to avoid a Polaris round trip on every query [S8].
- Side note relevant to the object-storage choice: ClickHouse's support matrix lists **SeaweedFS** itself as a catalog with Read, Create table, and INSERT all Beta, and the SeaweedFS guide describes an embedded Iceberg REST catalog whose S3 Table Buckets serve both catalog metadata and Parquet data behind one endpoint [S7][S19]. That is a different integration from Polaris and should not be conflated with it, but it is the one ClickHouse-documented path that combines SeaweedFS, Iceberg REST, and writes.

## Sources

All accessed 2026-09-27.

| ID | Source | Notes |
|----|--------|-------|
| S1 | ClickHouse docs, "Polaris catalog", https://clickhouse.com/docs/use-cases/data-lake/polaris-catalog (source: `github.com/ClickHouse/clickhouse-docs/blob/main/docs/use-cases/data_lake/reference/polaris.md`) | First-party Polaris guide. Last content commit 2026-03-31. Beta badge. States ClickHouse 26.1+. Contains the `allow_experimental_database_unity_catalog` note that contradicts other first-party sources. |
| S2 | ClickHouse docs, "REST catalog", https://clickhouse.com/docs/use-cases/data-lake/rest-catalog | Beta. `allow_database_iceberg = 1`. Iceberg tables only. |
| S3 | ClickHouse docs, "DataLakeCatalog", https://clickhouse.com/docs/reference/engines/database-engines/datalake | Supported catalogs, settings table, `force_add_bucket` Polaris wording. Page last modified 2026-09-25. |
| S4 | ClickHouse docs, "Iceberg table engine", https://clickhouse.com/docs/reference/engines/table-engines/integrations/iceberg | Type mapping, schema/write limitations, partition pruning, DROP PARTITION restriction, data cache, metadata cache, async prefetch. |
| S5 | ClickHouse docs, "iceberg" table function, https://clickhouse.com/docs/reference/functions/table-functions/iceberg | v1/v2/v3 support, deletion vectors, writes since 25.7, catalog section, metadata cache. |
| S6 | ClickHouse docs, "Data Lakes", https://clickhouse.com/docs/reference/datalakes | Iceberg REST Catalog entry. |
| S7 | ClickHouse docs, "Support matrix", https://clickhouse.com/docs/use-cases/data-lake/support-matrix | Catalog support table: Iceberg REST Read Beta, Create/INSERT no. Read-only statement. |
| S8 | ClickHouse docs, "Best practices for querying open table formats", https://clickhouse.com/docs/use-cases/data-lake/best-practices | Access methods, required settings, partition pruning, PREWHERE, caches, catalog latency, time travel, write settings. |
| S9 | ClickHouse docs, "Accelerating analytics with MergeTree", https://clickhouse.com/docs/use-cases/data-lake/accelerating-analytics | MergeTree advantages; ~283M row, ~9 second scan example. |
| S10 | ClickHouse source, `src/Core/Settings.cpp`, https://github.com/ClickHouse/ClickHouse/blob/master/src/Core/Settings.cpp | Version history and BETA/EXPERIMENTAL flags for `allow_database_iceberg` (24.12 new as `allow_experimental_database_iceberg`, alias 25.8), `allow_insert_into_iceberg` (25.7, Beta 26.2), `use_iceberg_partition_pruning` (25.1, default on 25.6), `iceberg_manifest_min_count_to_compact` (26.7). Read on `master` 2026-09-27. |
| S11 | ClickHouse source, `src/Core/SettingsEnums.cpp`, https://github.com/ClickHouse/ClickHouse/blob/master/src/Core/SettingsEnums.cpp | `catalog_type` string-to-enum mapping: `"rest"` to `ICEBERG_REST`, plus unity, glue, hive, onelake, biglake, paimon_rest, horizon, s3tables, delta_sharing. |
| S12 | ClickHouse source, `src/Databases/DataLake/RestCatalog.cpp` and `RestCatalog.h`, https://github.com/ClickHouse/ClickHouse/tree/master/src/Databases/DataLake | REST paths `/v1/{prefix}/namespaces/{namespace}/tables/{table}`, `/v1/config`, `X-Iceberg-Access-Delegation: vended-credentials`, `metadata-location`. Cross-checked at tag `v26.9.3.38-stable`: the header is added on the read path only under `if (result.requiresCredentials())` (line 1691-1693), and unconditionally only in `sendRequest` (line 1786, used by catalog DDL/mutation calls) and the refresh callback (line 2143). |
| S13 | ClickHouse source, `src/Databases/DataLake/ICatalog.h` | `TableMetadata` exposes location, schema, storage credentials; no data-read interface. |
| S14 | ClickHouse source, `src/Databases/DataLake/DatabaseDataLake.cpp` | Creates `StorageObjectStorage` / `StorageObjectStorageCluster` from the catalog-provided location; beta exception message for Iceberg REST. |
| S15 | ClickHouse source, `src/Databases/DataLake/DatabaseDataLakeSettings.cpp` | Setting defaults: `vended_credentials = true`, `auth_scope = 'PRINCIPAL_ROLE:ALL'`, `force_add_bucket = false` with Polaris wording. |
| S16 | ClickHouse Inc blog, "ClickHouse is data lake ready", 2026-08-31, https://clickhouse.com/blog/clickhouse-is-data-lake-ready | States catalog support began 24.12, "The Polaris catalog was supported as well", Iceberg support still beta with `allow_database_iceberg=1`. |
| S17 | GitHub releases, ClickHouse `v26.9.3.38-stable` (2026-09-26) and `v26.8.12.53-lts`, https://github.com/ClickHouse/ClickHouse/releases | Version pinning context. |
| S18 | ClickHouse docs, "Connecting to a data catalog", https://clickhouse.com/docs/use-cases/data-lake/connecting-catalogs | Lists REST Catalog, Lakekeeper, Nessie, Glue, OneLake; backtick namespace note. |
| S19 | ClickHouse docs, "SeaweedFS catalog", https://clickhouse.com/docs/guides/use-cases/data-warehousing/seaweedfs-catalog | SeaweedFS embedded Iceberg REST catalog; read/create/insert Beta. |
| S20 | ClickHouse docs, "Beta and experimental features", https://clickhouse.com/docs/reference/settings/beta-and-experimental-features | Definition of the Beta and Experimental labels used above. |
| S21 | ClickHouse `CHANGELOG.md`, https://github.com/ClickHouse/ClickHouse/blob/master/CHANGELOG.md | "Fix polaris catalog with azure" (26.4); REST `next-page-token` pagination fix (26.5); catalog listing predicate pushdown (26.7). |
| S22 | Peer research, `docs/research/04-polaris-authorisation-model.md` (team member `polaris-authz`), from Apache Polaris source at tag `apache-polaris-1.7.0` | Cross-reference only. Source of the no-STS / `stsUnavailable: true` behaviour and of the SeaweedFS STS interop test assertions (SeaweedFS 4.47 ships STS, so this is an interop question rather than a capability gap). Not independently verified in this note. |

## Verdict

**Yes. ClickHouse has a native, first-party integration with Apache Polaris, and it is delivered as the generic Iceberg REST catalog support in the `DataLakeCatalog` database engine with `catalog_type = 'rest'`, plus a dedicated first-party Polaris guide.** It speaks the Iceberg REST catalog protocol directly from ClickHouse source (`RestCatalog`), and ClickHouse Inc's own blog confirms Polaris has been supported since the 24.12 catalog work. The feature is **Beta, not GA**: the setting `allow_database_iceberg` carries the BETA flag in source, the source throws a "beta" message, and every first-party page shows a Beta badge. Through the catalog the integration is **read-only**: ClickHouse discovers tables, fetches schema, metadata location, and optional vended credentials from Polaris, then reads Parquet data files straight from object storage. The catalog does not carry data bytes. Writing requires loading into a native MergeTree table via `INSERT INTO SELECT`, or writing standalone (non-catalog) Iceberg tables on writable storage. **Confidence: high.**

The most load-bearing single citation is ClickHouse's own dedicated Polaris guide [S1], backed by the source-level beta gate and version history [S10][S14]. What would raise confidence further: stand up Polaris 1.1.0 against the actual SeaweedFS endpoint with a pinned ClickHouse 26.8 LTS (rather than reading `master`), capture the REST calls to confirm the exact endpoints and OAuth settings used, and confirm via object-storage access logs plus `system.query_log` that data reads hit storage directly and never the catalog. Two documentation inconsistencies should be re-checked against the pinned version: the Polaris guide's stray `allow_experimental_database_unity_catalog` instruction, and the `Settings.cpp` description that says `catalog_type = 'iceberg'` when the accepted string is `'rest'`.
