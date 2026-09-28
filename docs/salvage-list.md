# Salvage list: what the prior Olist repository contributes

**Status:** the assessment behind [ADR-0006](adr/0006-reference-only-reuse-and-provenance.md). It records what `github.com/SoongGuanLeong/data_pipelines_batch_stream_vector` contributes to this platform and what it does not.
**Evidence:** the read-only inventory at [`docs/research/09-olist-repo-inventory.md`](research/09-olist-repo-inventory.md), taken at commit `6f371903`.

## The rule

The prior repository is reference and design evidence. Nothing is copied. Every asset is read, and where its problem still exists here, the solution is written again against this platform's components and arrives with a test. A copy is permitted only as a recorded exception under ADR-0006.

This is not a verdict on the prior work. Its design thinking is well above its engineering maturity, and its own self-review says so in plain terms: the biggest gap is engineering maturity, not conceptual understanding. What transfers is the reasoning. What does not transfer is code written against MinIO, Trino and a notebook orchestrator, none of which exist here.

## Dispositions

**Confirmed feasible** means the prior repository proves the wiring works, and this platform builds its own version with components re-decided. **Design input** means a real problem was solved there; the design is read and the code is written here. **Superseded** means current practice has a better mechanism. **Void** means an earlier decision on this map already removed the component. **Deferred** means the decision belongs to another ticket, which receives the evidence.

| # | Asset (prior repo) | Disposition | Why |
|---|---|---|---|
| 1 | `cdc_stack` compose | Confirmed feasible | Debezium pgoutput into Kafka KRaft into a schema registry, with a topic browser and the connector auto-deployed. The posting's first-named path, and it composes in one file. Topology only; component versions belong to the technology-selection ticket. |
| 2 | `lakehouse_stack` compose | Void | Carries MinIO and Trino, both removed by earlier decisions. The Spark and Polaris service wiring survives as design input. |
| 3 | Trino Polaris catalog config | Void | Trino is out of scope. |
| 4 | Spark catalog config | Design input | The Polaris REST plus OAuth2 plus S3FileIO triple is the shape to write again, against the pinned Polaris and SeaweedFS. Its credential line and its MinIO endpoint are not carried. |
| 5 | Polaris bootstrap script (247 lines) | Design input | The highest-value asset in the repository: real RBAC and OAuth2 client-credentials automation against the Management API, with a multi-shape response fallback. Reimplement against the pinned Polaris. Its secret-minting-into-a-tracked-file behaviour is the leak mechanism and must not be reproduced. |
| 6 | Iceberg runtime `pom.xml` | Design input | The version-coordination knowledge is useful. The versions themselves are re-decided. |
| 7 | `gold/scd2.py` | Design input | 44 lines of textbook interval construction, with a deterministic tiebreaker and a reusable temporal-join predicate. Rewriting it costs less than auditing it, and the test is the real work either way. |
| 8 | `common/writers.py` key-replace writer | Superseded | See below. |
| 9 | Gold incremental impact propagation | Design input | The hardest and best logic in the repository, and entirely Olist-shaped. The problem, that a dimension change must ripple into the facts, recurs in any star schema. The code does not transfer. |
| 10 | Silver transform toolkit | Design input | Small, dependency-free helpers. `convert_accents` is Portuguese-specific; the rest are ten-line functions. |
| 11 | Avro decimal normaliser | Design input | A schema-introspecting conversion from an Avro decimal struct to a fixed-precision decimal. A real problem, worth solving again. |
| 12 | Schema-drift guard | Design input | The policy decision was made by the data-contracts item. The guard's shape was the starting point; it is rewritten with a major-version escape hatch, never carried. See `docs/data-contracts.md`. |
| 13 | Incremental reader watermark | Superseded | See below. |
| 14 | Iceberg table-property baseline | Design input | Format version, compression, target file size and hidden partitioning, stated once and applied consistently. Physical layout is the posting's stated emphasis, so these are starting values to be tuned against measurements, never settled values. |
| 15 | OLTP DDL, staging and load (916 lines) | Design input | A working pattern: a staging schema, an FK-ordered load, `ON CONFLICT DO NOTHING`, CDC-targeted indexes, and a publication that deliberately excludes the lookup tables. The DDL itself is Olist's schema. |
| 16 | Debezium connector config | Design input | pgoutput, the `ExtractNewRecordState` unwrap transform, delete rewriting, and the Avro converter set. The password and the host field are not carried. |
| 17 | Silver DQ modules (10 files) | Design input | A consistent per-table metric-collector convention, including change-operation, timestamp-null, future-dating and batch-id checks. Metrics were recorded and gated nothing, so the threshold, severity and gate design is this platform's own work. |
| 18 | SCD2 strategy design doc (276 lines) | Design input | Reading. Stateless recompute against stateful merge, copy-on-write against merge-on-read, with an honest recommendation and a migration path. The best single document in the repository. |
| 19 | Star schema and gold rules doc | Design input | Reading. Grain-first, safe-join and metric-integrity rules, plus an ERD that matches the code. |
| 20 | PySpark CI gate skeleton | Superseded | Lint-only over one directory, with an unpinned linter, which is why its green badge was an artifact rather than a gate. |
| 21 | Notebook 33 orchestration | Void | Dagster is the orchestrator. The concept, a run list, was right; a notebook driver with no retry, timeout or artifact capture is not a scheduler. |
| 22 | Do-not-carry list | Do not carry | `main.py`, the truncated `jobs/batch/build_bronze.py`, the generic `spark_pipeline_checklist.md`, the stale `project_stats.md`, the three `.bak` files, and the ELK compose whose log globs cannot match Spark's nested directories and whose filter block is empty. |

Counts: 1 confirmed feasible, 14 design input, 3 superseded, 3 void, 1 do not carry.

## Supersessions that carry constraints

### The key-replace writer

The prior writer replaces all rows for a set of keys by writing a uuid-namespaced staging table, issuing `DELETE FROM target WHERE EXISTS (SELECT 1 FROM staging ...)`, and then `INSERT INTO target SELECT FROM staging`. The inventory called it concurrency-safe and correct. It is concurrency-safe and it is not atomic: Iceberg commits the delete and the insert as two snapshots, so a reader between them sees the affected keys missing, and a failure after the delete leaves them deleted.

Verified 2026-09-27 against the Apache Iceberg source and documentation: Iceberg 1.10.x on Spark 4.0 supports `MERGE INTO ... WHEN NOT MATCHED BY SOURCE THEN DELETE`, which is the same key-scoped replacement in a single atomic snapshot commit. It is available from Iceberg 1.4.0, on format-version 2 and 3, and the row-level deletes it writes are position deletes (deletion vectors on format-version 3), never equality deletes.

Two things to carry. First, the precondition: the source must hold the complete recomputed row set for each key, which holds for a dimension rebuild and for the impact-propagation fact rebuilds, and does not hold for a plain row-level upsert. Second, a detail worth recording because it inverts the prior repository's own advice: its `merge_into` helper used a fixed staging table name with no uuid, so the MERGE variant was the concurrency-unsafe one, while the uuid fix went to the delete-and-insert function that did not need it.

### The incremental watermark

The prior reader derives its watermark from `MAX(spark_ingest_ts)` in the target table. That has a proven permanent-stall defect: the silver transforms filter rows out, so if a batch's newest row is dropped the watermark never advances and the range is re-read forever.

Verified 2026-09-27: there is no `streaming-snapshot-id`. Structured streaming supports only `stream-from-timestamp`. Bounded incremental reads exist but only through the DataFrame API, with `start-snapshot-id` exclusive and `end-snapshot-id` inclusive, and they are explicitly not available in Spark SQL. There is no end-of-changes marker, so the caller tracks the end snapshot itself.

The load-bearing finding is that **incremental reads are append-only**. A snapshot produced by MERGE, DELETE or overwrite makes the reader throw by default, or silently drop those changes if the skip flags are set. So a table maintained by MERGE cannot be consumed by the incremental reader, and the naive replacement of the old watermark with an incremental read would break on exactly the tables this platform cares about.

The replacement therefore splits by table shape. Append-only bronze reads incrementally through the DataFrame API, with its watermark snapshot id pinned by a tag, because tags never expire while `expire_snapshots` would remove the snapshot. MERGE-maintained silver and gold use a watermark control table advanced to the maximum input processed, which is the direct fix for the stall defect. Where a MERGE-maintained table must be consumed incrementally, `create_changelog_view` is the escape hatch, because it does capture updates and deletes.

Two items could not be verified and are not relied on: whether Iceberg documents a control table as the recommended watermark store (no such recommendation was found, so it is a conventional pattern rather than a documented one), and whether an expired `start-snapshot-id` errors or returns an empty read.

### The schema-drift policy

Resolved by [the data-contracts ticket](https://github.com/SoongGuanLeong/de-platform/issues/15). What that item received: a 25-line additive-only guard (`ALTER TABLE ADD COLUMN`, hard failure on column removal) and a genuinely validated evolution demonstration, where a column is added, written, read, dropped, and the registry-side version change is captured.

The guard was **not carried**. Ticket #15 decided that a breaking change is allowed as a new major contract version, so the additive-only hard failure was rewritten under [ADR-0006](adr/0006-reference-only-reuse-and-provenance.md) rather than copied, and extended with the version-bump escape: a drop, rename, narrow, optional-to-required, grain change or key change fails CI unless the same commit bumps the contract major, and at most two majors may coexist. The registry-side evidence is the Avro subject version change on the CDC topic (`<topic>-value`, `BACKWARD_TRANSITIVE`), captured through Apicurio's ccompat v7 endpoint, not screenshots. See `docs/data-contracts.md` and ADR-0019.

## What the Olist dataset decision does to this list

Decision #1 on this map recorded that Olist's data is CC BY-NC-SA 4.0 and that share-alike propagates to derived tables, so the data is a liability in a published portfolio even though its defects are excellent teaching material. This assessment therefore assumes Olist is not the dataset.

The condition, stated plainly: the **infrastructure half** (rows 1 to 6 and 14 to 16: stack wiring, catalog and connector configuration, the Iceberg property baseline, the DDL pattern) is applicable regardless of which dataset wins, because none of it depends on the source's shape. The **transformation half** (rows 9, 10, 11 and 17) is Olist-shaped, and its code is not applicable to any other dataset. The problems it solves, however, recur in any star schema, so it is recorded as design input rather than discarded.

If Olist were reinstated, only the transformation half would change status, and only from design input to a worked example. The reference-only rule would still apply, so no row ever becomes a port.

## Constraints carried forward

Four failures in the prior repository are properties of the environment rather than of its code, and this platform must not reproduce them.

- `host.docker.internal` in a connector config, with no `extra_hosts` entry, does not resolve on Linux. The new compose declares the host mapping explicitly.
- Both composes required environment variables with no defaults, and Compose substitutes empty strings for unset variables, so the documented first run could not work. This platform needs a documented environment contract, not a gitignore and hope.
- The Spark image build referenced a gitignored `target/jars/` directory produced by an undocumented manual Maven step, so the documented first run failed. Images must be built by a documented, reproducible step.
- A foreign-key script with no existence guard meant a second bootstrap run failed. Bootstrap must be idempotent by construction.

## Mapping from prior assets to this map's unspecified items

Recorded so those tickets do not re-derive work that already exists.

| Unspecified item | Prior asset | What it receives |
|---|---|---|
| Governance and data-quality specifics | Silver DQ modules (row 17) | A per-table metric-collector convention and four check shapes. Also the negative result: metrics that gate nothing, which is the gap the item exists to close. |
| Data contracts and schema compatibility policy | Schema-drift guard (row 12) | An additive-only guard, rewritten with a major-version escape hatch, and a validated schema-evolution demonstration with registry-side evidence. See `docs/data-contracts.md`. |
| The serving layer's concrete shape | Iceberg property baseline (row 14), gold rules doc (row 19) | The table-property baseline and the grain and join rules. No ClickHouse input: the prior repository had none. |
| Streaming job designs | none | Negative only. The prior repository has no Flink, and its Spark `foreachBatch` writer is not a streaming design. |
| Performance benchmark plan and baselines | none | No input. The prior repository contains no measurements, and this map's rule against fabricated numbers means nothing in it is usable as a baseline. |
| Repository decomposition | none | Negative only: the prior layout mixed notebooks, jobs, infra and source, with the orchestration living in notebooks. |
| Security model beyond the governance ticket | The credential incident | Four classes of committed credential and a mechanical root cause, recorded in ADR-0006. |
| Cloud topology and cost | none | No input. |
| The interview and demo narrative | The two candid self-reviews in `docs/architecture/` | A model for honest written assessment: both reviews name the real gaps accurately, which is the tone the portfolio's writeups should match. |
| The phased roadmap and its gates | none | No input. |

## What was checked and deliberately not changed

The claim that an upsert writes a key-only equality delete is correct for the Flink sink and was verified as wrong as a general statement, since Spark's MERGE writes position deletes. [ADR-0002](adr/0002-exactly-once-effect-not-delivery.md) is amended to scope it. Two research documents carry dated correction notes where they pair MERGE with equality deletes.

Four other places use the phrase loosely and were left alone: matrix row M3, which is scoped to Flink streaming jobs and therefore correct; the composite-key trap noted in `01a`, which is a real hazard on the Flink equality-delete path; the event-streaming report, which uses the phrase as a loose name for row deletes alongside tombstones; and the ClickHouse integration report, which already distinguishes position from equality deletes.
