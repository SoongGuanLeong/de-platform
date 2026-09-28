# 20 - Live test: ClickHouse 26.8 LTS reading an Iceberg v3 copy-on-write table

**Date of test:** 2026-09-28. All commands run on the local host described in the map Notes (12 CPU, 14 GB, rootless podman 5.7.0).

**Ticket:** [Full Iceberg v3 stack review](https://github.com/SoongGuanLeong/de-platform/issues/22). This document supplies the live evidence that section 8 of [16-clickhouse-iceberg-v3-read.md](16-clickhouse-iceberg-v3-read.md) said was still outstanding.

## The question

Can the pinned ClickHouse 26.8 LTS read an Iceberg format-version 3 table that has undergone a row-level operation in **copy-on-write** mode, and does it still fail hard on a v3 table that carries a Puffin **deletion vector**?

The claim under test is that format-version 3 is not the ClickHouse read blocker; only a Puffin deletion vector is. If true, a v3 copy-on-write table is readable on the pinned 26.8 with no serving change.

## Method

Two v3 tables were written by Spark 4.1.3 with the Iceberg 1.11.0 runtime, the platform's pinned writer set. Each was loaded with 100 rows and then had rows `id > 90` removed, so 90 rows remain. The only difference between them is the row-level operation mode. Both were then read by ClickHouse 26.8 LTS.

| Role | Image | Digest |
|---|---|---|
| Writer | `docker.io/apache/spark:4.1.3-java17` | `sha256:9b0a6c2c860f5e7d18dd5270286fef32a09c7f5a7e2b0dbe5642de8a3a02ab3e` |
| Reader | `docker.io/clickhouse/clickhouse-server:26.8.13.2` | `sha256:d3cdda9b2137852b20b96b1262b043dbedbe78c2b2c7063a3da60781a29e3463` |

Iceberg runtime: `org.apache.iceberg:iceberg-spark-runtime-4.1_2.13:1.11.0`. Spark reports `Apache Iceberg 1.11.0 (commit 6976e020b894f6a6777704df2b8c4458cb291ae9)`.

The reader used ClickHouse's `icebergLocal` table function over the local filesystem. The platform's read-through arm uses `DataLakeCatalog` with `catalog_type='rest'` against Polaris instead; see the caveats.

## Case 1, copy-on-write: reads correctly

Table properties: `format-version=3`, `write.delete.mode=copy-on-write`, `write.merge.mode=copy-on-write`.

Current snapshot summary as written by Spark:

```
operation: overwrite
added-data-files: 1, deleted-data-files: 2
total-records: 90
total-data-files: 11
total-delete-files: 0
total-position-deletes: 0
total-equality-deletes: 0
format-version: 3
next-row-id: present
```

No delete files of any kind were produced. The metadata carries `next-row-id`, a v3 marker.

ClickHouse 26.8.13.2 read:

```
SELECT count(*), min(id), max(id), sum(id) FROM icebergLocal('.../db/t') FORMAT TSV
90	1	90	4095
```

`sum(id)` for the 90 surviving rows (1 to 90) is 4095, so the deletes were applied, not ignored. No error, no warning.

## Case 2, merge-on-read: fails hard, as predicted

Table properties: `format-version=3`, `write.delete.mode=merge-on-read`, `write.merge.mode=merge-on-read`.

Current snapshot summary as written by Spark:

```
operation: delete
added-delete-files: 2, added-dvs: 2, added-position-deletes: 10
total-records: 100
total-delete-files: 2
total-position-deletes: 10
format-version: 3
```

A `-deletes.puffin` file is present in the table's `data/` directory, so this is a genuine v3 deletion vector, not a legacy position-delete file.

ClickHouse 26.8.13.2 read:

```
Code: 36. DB::Exception: Position deletes are supported only for parquet format:
While executing ReadFromObjectStorage. (BAD_ARGUMENTS)
```

This is the exact error and error code predicted from source in section 8 of the ClickHouse research document.

## Verdict

**Confirmed on a live pinned 26.8 LTS binary.** Format-version 3 is not the ClickHouse read blocker. A v3 table whose row-level operations run in copy-on-write mode carries no delete files and is read correctly; a v3 table with a Puffin deletion vector fails hard with `BAD_ARGUMENTS`. The negative control rules out the possibility that the harness simply cannot detect the failure.

This underwrites the ticket decision to place the schema-evolution demonstration on a v3 copy-on-write table and keep the pinned ClickHouse 26.8 LTS.

## Caveats

- **The REST catalog path was not exercised.** The platform's read-through arm reads through `DataLakeCatalog` with `catalog_type='rest'` against Polaris. This test read through `icebergLocal` over the filesystem. Both paths share ClickHouse's Iceberg read code, including the `PositionDeleteTransform` that throws, so the finding is expected to transfer, but the REST path itself is untested here.
- **Single host, rootless podman 5.7.0.** The host's podman is end-of-life (map Notes pin 6.1.1 or later for the platform). The container runtime version does not affect the ClickHouse or Iceberg behaviour under test.
- **Small data.** 100 rows in 12 data files. This tests metadata and delete-file handling, not scan performance.
- **Writer was Spark only.** The Flink v3 upsert path is unverified at the pinned tag and is not covered by this test.

## Reproduction

```bash
# Writer, copy-on-write
podman run --rm -v "$PWD/run:/work" -w /work docker.io/apache/spark:4.1.3-java17 \
  /opt/spark/bin/spark-sql \
  --jars /work/iceberg-spark-runtime-4.1_2.13-1.11.0.jar \
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
  --conf spark.sql.catalog.local=org.apache.iceberg.spark.SparkCatalog \
  --conf spark.sql.catalog.local.type=hadoop \
  --conf spark.sql.catalog.local.warehouse=/work/warehouse \
  -f /work/create.sql

# Reader
podman run --rm -v "$PWD/run:/work" docker.io/clickhouse/clickhouse-server:26.8.13.2 \
  clickhouse local --query "SELECT count(*) FROM icebergLocal('/work/warehouse/db/t')"
```

Note for anyone re-running: the Spark image runs as uid 185, so the mounted work directory must be writable by that user.
