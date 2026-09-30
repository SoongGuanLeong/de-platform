# Data contracts and schema compatibility: contracts, versioning, interfaces and evolution

**Ticket:** [Data contracts and schema compatibility policy](https://github.com/SoongGuanLeong/de-platform/issues/15)
**Map:** [Vendor-neutral lakehouse data platform: architecture proposal](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Target posting:** ONL Biz Solutions, Senior Data Engineer - Data Lakehouse ([JobStreet 94703893](https://my.jobstreet.com/job/94703893)), cached verbatim at `~/projects/career-ops/data/jd-cache/031.md`.
**Decision records:** [ADR-0019](adr/0019-contracts-are-contract-first-and-break-by-version.md), [ADR-0020](adr/0020-avro-on-the-cdc-topics-with-backward-transitive-compatibility.md), [ADR-0021](adr/0021-the-consumer-interface-is-the-versioned-serving-views.md), [ADR-0022](adr/0022-iceberg-format-v2-is-pinned.md), [ADR-0023](adr/0023-rollback-restores-the-iceberg-table-only.md), [ADR-0025](adr/0025-iceberg-v3-copy-on-write-for-schema-evolution.md).

---

## 1. What this document is

The concrete shape of the platform's contract and schema-compatibility layer: what a contract is and where it lives, what counts as a breaking change and what happens when one lands, the compatibility rule per surface, the consumer-facing interface and its versioning, the schema-evolution matrix applied to named tables, and the rollback and per-operation cost design.

It resolves [the data-contracts ticket](https://github.com/SoongGuanLeong/de-platform/issues/15) on the map, which holds M9's data contract and backend-facing interface requirement and M17's schema-evolution matrix.

It is a design, not a result. Nothing here has been measured, and no latency, file count, byte figure or row count appears. Every threshold is deferred to `docs/budgets.yaml` and committed before the measurement it judges.

## 2. The contract: home, format and authority

**One machine-readable YAML contract per gold table, at `contracts/<spine>/<table>.yml`, and one `contracts/interface.yml` platform index.** YAML rather than Markdown because CI must parse it, and because the completion bar's "CI fails on an unclassified new column" is only a mechanical check if the classifier is machine-readable.

The contract is the **single source of truth** for its table. The completion bar fixes most of its fields, ADR-0017 adds the per-column PII class, the governance document adds the business checks, and this ticket adds the timestamps and the serving mapping. The field set:

```yaml
table: commerce.gold.fact_order_line
spine: commerce
layer: gold
grain: one row per order line
contract_version: 1.0
source:
  topic: tpc-c.public.order_line
  subject: tpc-c.public.order_line-value
  compatibility: BACKWARD_TRANSITIVE
timestamps:
  event_time: o_entry_d
  as_of: null
  valid_from: null
  valid_to: null
columns:
  - {name: w_id, type: int, nullable: false, pii_class: none}
  - {name: ol_quantity, type: int, nullable: false, pii_class: none}
  - {name: ol_amount, type: decimal(12,2), nullable: false, pii_class: none}
business_keys: [w_id, d_id, o_id, ol_number]
invariants:
  - ol_quantity > 0
quality:
  business_checks:
    - {id: b_order_line_non_negative_amount, severity: fail}
persona_queries: [O1, O2, O3]
serving:
  - {database: commerce, view: fact_order_line_v1, status: live}
versioning:
  rule: additive-within-major
  breaking: [drop_column, rename_column, narrow_type, optional_to_required, grain_change, key_change]
```

**What reads what.** The DQ `schema` check is **generated** from this file, so the column list is written once and not twice. The `record`, `pipeline`, `business` and `source` checks stay hand-written, because they assert things the schema does not carry. There is exactly one writer per fact.

Every column carries a `pii_class` (ADR-0017). A table that retains a sensitive column classifies it here, as `dim_customer_tpch` does for `c_phone` (`direct`). TPC-C's PII columns are silver-only, so they do not appear in a gold contract at all.

**Where the table definition lives.** The completion bar said the contract sits "next to its definition", but the definitions' home is [the repository-decomposition ticket](https://github.com/SoongGuanLeong/de-platform/issues/16), which is still open. The `contracts/` tree is fixed now and **CI resolves the table's location from the contract's `table` field**, so #16 relocating the definitions is a move rather than a contract rewrite.

**`contracts/interface.yml` is an index with a policy, not a second column list.** It carries view name, the gold contract it serves, the view version, its status (`live` or `deprecated`), and the interface versioning rule. Per-column detail stays only in the gold contract.

```yaml
interface_version: 1
views:
  - {view: fact_order_line_v1, contract: commerce/gold/fact_order_line.yml, version: 1, status: live}
versioning:
  rule: additive-within-a-view-version
  breaking: new-view-version
```

## 3. Versioning: what counts as breaking, and the consequence

**Contract versions are `major.minor`.** A minor bump is an additive, backward-compatible change. A major bump is required for a breaking one. The breaking set is fixed: drop a column, rename a column, narrow a type, turn an optional column required, change the grain, change the business key. Additive changes are permitted and update the contract in the same commit: add an optional column, widen `int` to `long`, widen `float` to `double`, widen `decimal(P, S)` to `decimal(P', S)` where `P' > P`.

**A breaking change is never made in place.** It lands as a new contract version. Because the platform has only declared consumers, the migration is the consumer's, and the old version is kept until the next breaking version supersedes it.

**At most two major versions live at once, and a deprecated major is retained until the next breaking version supersedes it.** The window is a count, not a calendar, because the platform has no release cadence and a date-based window would be a guess wearing a policy's clothes. CI asserts the count.

**The CI guard.** A drop, rename, narrow, optional-to-required, grain change or key change **hard-fails unless the same commit bumps the contract major**, in which case it is allowed and the old major is retained. The guard is the salvage list's 25-line additive-only check **rewritten** under [ADR-0006](adr/0006-reference-only-reuse-and-provenance.md) (reference only, no code copied), extended with the version-bump escape. The salvage list's "schema-drift policy" section is corrected accordingly.

**Falsifiable evidence:** the same drop fails on a commit that does not bump the major and passes on one that does; and a third live major fails the coexistence assertion. Adding a column without a `pii_class` fails CI (ADR-0017). Removing a column without a version bump fails CI.

## 4. The compatibility rule per surface

The compatibility rule only bites where a machine reads the schema. There are four surfaces, and they do not share one rule.

| Surface | Rule | Enforced by |
|---|---|---|
| The CDC Kafka topic | Avro, subject `<topic>-value`, `BACKWARD_TRANSITIVE` | The serializer, against Apicurio's ccompat v7 endpoint |
| The gold Iceberg tables | The contract: validated as a file in CI, asserted against the live table under a path profile ([the testing strategy](testing-strategy.md) section 7) | CI plus the batch or streaming profile |
| The ClickHouse serving copy | None of its own; it is derived | The contract's rule, inherited |
| The consumer-facing interface | The view version rule, section 5 | The interface policy and CI |

**The CDC topic carries Avro, not `debezium-json`.** The subject is `<topic>-value` (Debezium's default topic naming, the Confluent subject convention), one per CDC topic, mode `BACKWARD_TRANSITIVE`. The producer is Debezium's Kafka Connect `AvroConverter` in `as-confluent` mode; the reader is Flink's `avro-confluent` format, both pointed at Apicurio's `/apis/ccompat/v7`.

Two reasons, and the second is the load-bearing one. Completion bar 6.1's falsifiable test is that "a backward-incompatible schema is **rejected by the serializer**", and only a registry-backed serializer can do that; choosing JSON would quietly downgrade that evidence item to a CI check. And the platform replays partitions from offset 0 (M2's idempotence test) and reads historical data through the read-through arm, so every *historical* consumer must still read new data, which is what `BACKWARD_TRANSITIVE` means and plain `BACKWARD` does not.

**Correction, 2026-09-28 (ticket #15).** This **amends** the earlier `debezium-json` reading. Research 06 recommends `debezium-json` as *a* standard way to feed upsert mode, and research 11 read that as the platform's choice; both carry dated correction notes, as does [ADR-0020](adr/0020-avro-on-the-cdc-topics-with-backward-transitive-compatibility.md).

**The gold contracts are pushed into Apicurio's native Data Contracts feature by CI as a mirror, never authored there.** The registry can then answer "what version is this table's contract at" without becoming a second source of truth. The registry's ccompat path accepts data-contract rules but does not store or enforce them (research 11, [S8]), so the native feature is the only place the mirror can live.

**Bronze and silver carry no contract files.** Bronze is governed by the Avro subject and silver by the `schema` check run against it. Neither is given a file for symmetry.

## 5. The consumer-facing interface

**The interface is the versioned ClickHouse serving views, with the Iceberg gold tables named as the second, read-only interface.** M9 names "a backend-facing interface contract with explicit versioning rules" and the posting names backend engineers separately from analysts. The serving views are the only consumer-facing surface the platform actually builds, the operations persona (O1 to O3) is the near-real-time path a backend would integrate against, and a versioned view name is a mechanism rather than a promise. The Iceberg tables are the second interface because a backend can read them through the catalog with the vended credential, and that path is already governed (M10).

**A REST or API surface is explicitly rejected.** No requirement names one, and inventing one is surface area without engineering depth, the same reasoning that ruled out Superset and Trino.

**Versioning rule:** additive within a view version; a breaking change is a new `_vN` view with the old one kept, and the persona query ids in the contract are the consumer simulation that proves the old view still answers. The view's status moves to `deprecated` in `interface.yml` when its successor is created.

## 6. The schema-evolution matrix

M17 asks for five operations, each applied with its read paths verified. The platform has two write paths (Flink upsert, Spark `MERGE`) and four read paths (Spark, ClickHouse `DataLakeCatalog` read-through, the ClickHouse materialised copy, and Polaris `loadTable`).

**Two representative tables, one per write path, plus the SCD2 case.** `commerce.gold.fact_order_line` (Flink-upsert-written) and `commerce.gold.fact_lineitem` (Spark-written, and TPC-H's published answers give the read assertion an oracle). `dim_postcode` is named as the SCD2-specific extra, because its `as_of` and validity semantics make rename and drop behave differently there.

**Every operation is verified through all four read paths**, not only Spark. Only the `add-required-with-default` row needs a table on format v3, and it is the only row whose table is not v2.

**The add-optional row runs as one continuous chain**, because that is the demonstration the salvage list asks for and five disconnected `ALTER TABLE` statements would evidence Iceberg but not the platform: add the field to the Avro topic (subject v1 to v2), Flink sink, the gold contract updated, the ClickHouse copy re-materialised, and the persona query still answering.

**The add-required-with-default row runs on the v3 copy-on-write table.** At format v2 a required column cannot be added to a non-empty table: Iceberg's `initial-default` and `write-default` are a format-v3 feature, and adding a required field requires both to be non-null. `commerce.gold.fact_lineitem` therefore moves to format v3 with `write.delete.mode` and `write.merge.mode` set to `copy-on-write`, which produces no delete files and is what keeps the row readable by ClickHouse 26.8 (ADR-0025). The column is added through the Iceberg API rather than Spark SQL, because `ALTER TABLE ... ADD COLUMN ... DEFAULT` throws unsupported; the SQL limitation is recorded rather than hidden.

### 6.1 Why the gold tables are format v2, and which one is not

Iceberg's column defaults are v3-only, so staying on v2 has a real cost. The constraint is the **serving reader's handling of deletion vectors**, not the format version: ClickHouse 26.8 LTS has no format-version read gate and reads v3 tables that carry no deletion vectors, and it fails hard with `BAD_ARGUMENTS: Position deletes are supported only for parquet format` on a v3 table carrying a Puffin deletion vector.

Verified live 2026-09-28 on the pinned `26.8.13.2` binary: a v3 copy-on-write table was read correctly, and a v3 merge-on-read table carrying a Puffin deletion vector failed with the error above. The method and evidence are in `docs/research/20-clickhouse-26-8-v3-copy-on-write-live-test.md`. Deletion-vector read support merged into `26.10.1.35` (ClickHouse issue #107502, resolved by PR #110781); 26.10 is a non-LTS release and the feature is labelled Experimental, and the next LTS containing it is 27.3 (March 2027), because new features are not backported.

Every gold table is `MERGE`-maintained, and a merge-on-read row-level operation on a v3 table produces a deletion vector, so every merge-on-read gold table stays v2. `commerce.gold.fact_lineitem` is the one exception: it runs copy-on-write, produces no delete files, and is therefore on v3 (ADR-0025). The earlier reason recorded in `docs/streaming-jobs.md` ("version 3 is partially supported across the readers") was directionally right but imprecise, and the reason previously recorded here named the format version rather than the deletion vector. Both are corrected.

**The full-v3 question is settled** by [Full Iceberg v3 stack review](https://github.com/SoongGuanLeong/de-platform/issues/22) and recorded in ADR-0025. Two validation items remain open and are documented limitations rather than decisions: the read-through arm's REST catalog path was not exercised by the live test, which read through `icebergLocal` over the filesystem, and the Flink v3 upsert writer is unverified at the pinned tag.

### 6.2 The partition-transform restriction

A type promotion is not allowed on a column that feeds a partition transform if the transform's value would change. This is not hypothetical here: `fact_order_line` is partitioned by `days(o_entry_d)`, so the `o_entry_d` column's type cannot be promoted without checking the transform. The matrix's type-change row is run on a non-partition column for this reason, and the restriction is recorded as a property of the table, not of the operation.

## 7. Rollback and the serving copy

**Rollback is `CALL iceberg.system.rollback_to_snapshot(...)` on one gold table to the snapshot before a deliberately bad write, asserted by the persona query returning its pre-change oracle value.** The representative table is `fact_order_line`.

Two things rollback does **not** do, and both are recorded because the assumption that it does them is the natural one:

- **It does not propagate to the ClickHouse serving copy.** The copy must be re-materialised after the rollback, and the runbook names that step.
- **It does not restore the schema, only the data.** Field deletion cannot be rolled back unless the field was nullable or the current snapshot has not changed since the delete, so the schema half of a rollback is a separate contract-version operation.

**The relationship to ADR-0016 is explicit.** Rollback is the manual form of the branch fast-forward that ADR-0016 uses to promote a batch: both must agree on what "the previous good state" means, and both define it as the last snapshot whose persona queries returned their oracle values. The two must not drift, so the definition lives here and ADR-0016's gate cites it.

## 8. The per-operation cost design

M17 asks for "a measured cost for each operation: metadata growth, commit latency, orphan-file cleanup". The design fixes the counters now; the numbers are produced during implementation.

| Counter | How it is measured |
|---|---|
| Commit latency | Wall-clock elapsed for the relevant `ALTER`, `MERGE` or `rollback` operation |
| Metadata growth | Metadata-object and row growth in the `snapshots`, `manifests` and `files` metadata tables, **and byte growth where measurable**. Row counts alone are never presented as storage-byte growth |
| Snapshot expiry | Old snapshots, references and files removed by `expire_snapshots` |
| Orphan cleanup | Orphan files removed and bytes reclaimed by `remove_orphan_files`, measured separately from expiry |

**The five `m17-*` entries are in `docs/budgets.yaml`**, declared before the schema-evolution matrix is run and cited by the matrix's evidence items. This document names the counters; it does not claim numbers. The completion bar's honesty rule forbids a measured number while the map is open, and the protocol that produces them is [the benchmark plan](benchmark-plan.md) section 2.

## 9. What this document does not decide

- **Where the table definitions live.** Owned by [#16](https://github.com/SoongGuanLeong/de-platform/issues/16). The contract path and the CI resolution rule are fixed here so that ticket is a move, not a redesign.
- **The benchmark protocol and its profiles.** Owned by the completion bar's Tier B evidence.

## 10. Constraints carried forward

1. A breaking change is never made in place; it is a new contract version (ADR-0019).
2. At most two contract majors live at once, asserted by CI (ADR-0019).
3. The CDC topic carries Avro with `BACKWARD_TRANSITIVE`, enforced by the serializer (ADR-0020).
4. The Git YAML contract is the sole authoring source; the registry copy is a CI-pushed mirror (ADR-0020).
5. There is no REST or API surface; the interface is the versioned serving views (ADR-0021).
6. The gold tables are Iceberg format v2 except `commerce.gold.fact_lineitem`, which is v3 copy-on-write, and the add-required-with-default row is demonstrated on it through the Iceberg API (ADR-0025).
7. Rollback restores the Iceberg table only; the serving copy is re-materialised (ADR-0023).
8. No em dashes, use a hyphen.
