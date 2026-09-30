# The data architecture: the two spines, the layers and the physical layout

**Ticket:** [The architecture synthesis: system architecture, data architecture and data-flow diagrams](https://github.com/SoongGuanLeong/de-platform/issues/26)
**Map:** [Vendor-neutral lakehouse data platform: architecture proposal](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Target posting:** ONL Biz Solutions, Senior Data Engineer - Data Lakehouse ([JobStreet 94703893](https://my.jobstreet.com/job/94703893)), cached verbatim at `~/projects/career-ops/data/jd-cache/031.md`.
**Decisions recorded here:** no new ADR. It consolidates [ADR-0008](adr/0008-two-spines-with-no-cross-domain-join.md) (the spines), [ADR-0016](adr/0016-gate-on-input-and-promote-through-a-branch.md) (the gate), [ADR-0018](adr/0018-time-bounded-kafka-retention-for-cdc.md) (retention) and [ADR-0025](adr/0025-iceberg-v3-copy-on-write-for-schema-evolution.md) (format version).

---

## 0. Status

No platform code exists while the map is open. **Nothing in this document was measured.** Every partition, key, format version, TTL and file-size figure is a declared baseline for a benchmark to test.

**Where a value appears here and in a per-domain spec, the per-domain spec is the authority and this document restates it for the reviewer's convenience.** The consolidated tables carry a column naming that authority, and a [structural check](ci-cd-strategy.md) asserts the two agree on the keyed set.

## 1. What this document is

The mission's Final Deliverables item 5 ("data architecture"). The per-domain specs decided the spine split, the grains, the sink configuration and the serving layout separately; this document is the single view of all of them, so that a reviewer does not have to hold four documents in mind to see one table's full physical shape.

## 2. The two spines

Four sources, two spines, and **nothing joins them**. The only cross-spine link is a clock. Detail in [the dataset selection](dataset-selection.md) section 3 and [ADR-0008](adr/0008-two-spines-with-no-cross-domain-join.md).

| Spine | Source | Ingestion | Processing | Role |
|---|---|---|---|---|
| **Commerce** | TPC-C on live PostgreSQL | Debezium CDC to Kafka, Avro via Apicurio | Flink upsert to Iceberg; Spark for gold | The CDC centre of gravity, and the only source with real binlog change events |
| **Commerce** | TPC-H SF100 | Batch file | Spark batch silver and gold to Iceberg; materialise to ClickHouse | The batch and serving centre, with published answers as the oracle |
| **Network** | RIPE Atlas | The collector: live WebSocket, plus a REST backfill producer into the same topic | Flink streaming to Iceberg, with a declared watermark and lateness | The streaming centre of gravity, at-most-once and genuinely messy |
| **Network** | ONSPD | Batch file, quarterly releases | Spark batch, SCD2 `MERGE` into Iceberg | Geography, SCD2 history, and the publisher's own documented defects |

**Three constraints that shape every table below.**

- **No cross-spine join, and a domain relationship is not a key join.** TPC-C and TPC-H share a subject matter and share no key.
- **No conformed geography dimension spans the platform.** Geography is a network-spine concept only, because TPC-C's addresses have no real-world referent and TPC-H's `nation` and `region` are fictional.
- **The one genuine cross-source join is inside the network spine**: RIPE Atlas probe coordinates to ONSPD postcodes, spatial and approximate, with a documented tolerance.

## 3. The layers, and the naming convention

Both spines have the same three layers, and a fourth namespace holds the control-plane tables.

| Layer | What it holds | Write path |
|---|---|---|
| **Bronze** | The source's own records as they arrived, landed without business transformation | Flink for the streaming sources, Spark for the batch sources |
| **Silver** | Cleansed, typed, deduplicated and conformed, at the source's own grain | Spark for both spines |
| **Gold** | The modelled tables the serving layer and the analysts read, with declared grains and contracts | Flink for the CDC facts and the RIPE results; Spark for everything else |
| **`platform`** | Control-plane tables: the quarantine table and control state. Not a spine and not a layer | The gate, and the retention asset |

**Naming.** Iceberg tables are `<spine>.<layer>.<table>` in the Polaris namespace, which is spine-then-layer: `commerce.bronze`, `commerce.silver`, `commerce.gold`, `network.bronze`, `network.silver`, `network.gold`, and `platform`. ClickHouse mirrors the serving domains in four databases: `commerce`, `network`, `governance` and `lakehouse`, the last holding the read-through comparison arm.

**Two naming consequences worth stating.** The `commerce` namespace is shared by two sources, so TPC-H's customer dimension is suffixed `dim_customer_tpch`; and TPC-C's customer dimension is silver-only because it carries PII, so the name `dim_customer_tpcc` is **reserved rather than used**.

## 4. The gold inventory and its grain

Grain is what one row represents, and it is the decision M6 exists to test. Full reasoning in [the serving layer](serving-layer.md) section 4.

| Spine | Table | Grain |
|---|---|---|
| Commerce, TPC-H | `fact_lineitem` | Line grain, one row per order line |
| Commerce, TPC-H | `dim_customer_tpch`, `dim_part`, `dim_supplier`, `dim_nation`, `dim_region`, `dim_date` | One row per entity |
| Commerce, TPC-C | `fact_order_line` | Order-line grain, with the order header denormalised on |
| Commerce, TPC-C | `fact_stock` | One row per (warehouse, item) |
| Commerce, TPC-C | `fact_delivery` | Order grain |
| Network, RIPE Atlas | `fact_measurement_result` | Result grain |
| Network, RIPE Atlas | the per-minute probe aggregate | One row per probe per one-minute tumbling window |
| Network, RIPE Atlas | `dim_probe`, `dim_measurement` | One row per entity |
| Network, ONSPD | `dim_postcode` | SCD2, with `valid_from` and `valid_to` from `DOINTR` and `DOTERM`, null meaning live |
| Network, ONSPD | `postcode_geography` | A bridge table, because one postcode maps to several geographies in the straddling cases |

**There is deliberately no `fact_orders`.** Order-grain and line-grain measures sitting side by side is the trap the C2 query exists to expose.

## 5. The physical layout, consolidated

### 5.1 The Iceberg side, which is the record

| Table | Format | Partition | Upsert and equality fields | Authority |
|---|---|---|---|---|
| `commerce.gold.fact_order_line` | v2, merge-on-read upsert | `days(o_entry_d)` | PK `(w_id, d_id, o_id, ol_number)` union `o_entry_d` | [streaming-jobs](streaming-jobs.md) 4.2 |
| `commerce.gold.fact_delivery` | v2, merge-on-read upsert | `days(o_entry_d)` | PK `(w_id, d_id, o_id)` union `o_entry_d` | [streaming-jobs](streaming-jobs.md) 4.2 |
| `commerce.gold.fact_stock` | v2, merge-on-read upsert | none | PK `(s_w_id, s_i_id)` | [streaming-jobs](streaming-jobs.md) 4.2 |
| `commerce.gold.fact_lineitem` | **v3, copy-on-write** | not fixed; an M5 open measurement | Batch `MERGE`, no upsert sink | [ADR-0025](adr/0025-iceberg-v3-copy-on-write-for-schema-evolution.md) |
| `commerce.gold.dim_*` | v2 | not fixed | Batch `MERGE` | [serving-layer](serving-layer.md) 4 |
| `network.gold.fact_measurement_result` | v2, merge-on-read upsert | `days(measurement_ts)` | `result_id` union `measurement_ts` | [streaming-jobs](streaming-jobs.md) 5 |
| `network.gold` per-minute probe aggregate | v2, merge-on-read upsert | not fixed | The window key union the probe | [streaming-jobs](streaming-jobs.md) 5 |
| `network.gold.dim_probe`, `dim_measurement`, `dim_postcode`, `postcode_geography` | v2 | not fixed | Batch `MERGE`; `dim_postcode` is SCD2 | [serving-layer](serving-layer.md) 4 |
| `platform.quarantine` | v2 | not fixed | Append-only, keyed by `_run_id` | [governance](governance-and-data-quality.md) 4 |

**The equality fields are the declared primary key union every partition source column**, because Iceberg fails the upsert precondition when a partition source column is missing from the key. This is why **a changed partition transform changes the equality fields**: the two are decided together, and M5 tests the transform on one hot table.

**The v3 exception is one table, and it is copy-on-write on purpose.** ClickHouse 26.8 LTS fails on a v3 table carrying a Puffin deletion vector, so every table that Flink upserts into stays v2 (upsert requires merge-on-read, which carries deletion vectors), and only `commerce.gold.fact_lineitem` runs v3 with copy-on-write so that M17 can demonstrate add-required-with-default. The trigger for revisiting is an LTS that reads deletion vectors.

### 5.2 The ClickHouse serving copies

`PRIMARY KEY` stays equal to `ORDER BY` throughout, the ClickHouse default, so the declaration matches `system.tables.sorting_key` and `system.tables.primary_key`, which [the completion bar](completion-bar.md) checks.

| Table | Engine | Partition | `ORDER BY` | TTL | Refreshed by |
|---|---|---|---|---|---|
| `fact_lineitem` (P1) | MergeTree | `toYYYYMM(l_shipdate)` | `(l_shipdate, l_partkey, l_suppkey)` | none | Spark, partition swap |
| `dim_customer_tpch`, `dim_part`, `dim_supplier` (P1) | MergeTree | none | business key | none | Spark, partition swap |
| `dim_nation`, `dim_region`, `dim_date` (P1) | MergeTree | none | key | none | Spark, partition swap |
| `fact_measurement_area` (P2) | MergeTree | `toStartOfHour(ts)` | `(ts, postcode_area, probe_id)` | `ts + 90 days` | Spark, partition swap |
| `measurement_hourly_by_area` (P2) | AggregatingMergeTree via materialised view | `toYYYYMM(hour)` | `(postcode_area, hour)` | none | The materialised view |
| `dim_postcode` (P2) | MergeTree | none | `(postcode, valid_from)` | none | Spark, partition swap |
| `postcode_geography` (P2) | MergeTree | none | `(postcode, geography_type, geography_code)` | none | Spark, partition swap |
| `fact_order_line` (P3) | ReplacingMergeTree(`lsn`) | `toYYYYMM(o_entry_d)` | `(w_id, d_id, o_id, ol_number)` | 365 days | Flink, keyed replacement |
| `fact_stock` (P3) | ReplacingMergeTree(`lsn`) | none | `(s_w_id, s_i_id)` | none | Flink, keyed replacement |
| `fact_delivery` (P3) | ReplacingMergeTree(`lsn`) | `toYYYYMM(o_entry_d)` | `(w_id, d_id, o_id)` | none | Flink, keyed replacement |

Codecs and the single projection (`proj_supplier` on `fact_lineitem`) are in [the serving layer](serving-layer.md) section 7 and are not repeated here.

**The two TTLs are serving-window decisions, not retention decisions.** Iceberg remains the record and holds the full history, and the M2 reconciliation compares the source against Iceberg rather than against ClickHouse. The TPC-H fixture carries no TTL at all, because deleting rows would destroy the published-answer oracle.

## 6. The serving copies, and how they stay current

ADR-0003 fixes the architecture: ClickHouse holds materialised MergeTree copies, and catalog read-through is retained only as the measured comparison arm. The split is **batch by default, streaming for named exceptions**.

- **Batch-materialised by Spark:** the TPC-H star for the commercial analyst, and the network tables for the network analyst. The mechanism is a partition-scoped rebuild with an atomic `ALTER TABLE ... REPLACE PARTITION`, so a reader sees the old partition or the new one and never a gap.
- **Streaming-materialised by Flink:** `fact_order_line`, `fact_stock` and `fact_delivery` for the operations analyst. This is the single named streaming exception, and it exists because a late update can touch an arbitrarily old partition, so there is no bounded partition set to rebuild. Convergence is carried by `ReplacingMergeTree` versioned by the source LSN, because the official connector's sink is at-least-once.
- **Iceberg-only:** everything else. Bronze and silver have no serving copy at all.

The network copy is **shaped**: the resolved `postcode_area` is baked onto `fact_measurement_area` at materialisation, and N3 is served by the hourly rollup rather than by rescanning raw results.

## 7. What is deliberately not enumerated

Two gaps, registered rather than filled with invented names.

- **The bronze and silver table inventory is not fixed.** The layer semantics and the naming convention are (section 3), and the tables that are already named elsewhere are named here; but a per-table bronze and silver inventory would be invented in this document and would then bind the contracts and the implementation. It lands with the contracts and the implementation instead.
- **The Iceberg-side partition transform and sort order for the batch-written gold tables are not fixed.** They are decided for the tables Flink writes, because the upsert precondition forces the partition into the equality fields. For the Spark-written tables they are an M5 open measurement.

## 8. Named constraints

1. Nothing here is measured.
2. No cross-spine join, and no conformed geography dimension ([ADR-0008](adr/0008-two-spines-with-no-cross-domain-join.md)).
3. Format v2 everywhere except `commerce.gold.fact_lineitem`, which is v3 copy-on-write ([ADR-0025](adr/0025-iceberg-v3-copy-on-write-for-schema-evolution.md)).
4. Every `fact_lineitem` layout value is a baseline the B1 sweep tests.
5. The M2 reconciliation is against Iceberg, never against ClickHouse.

## 9. Open measurements and one recorded discrepancy

- **The Iceberg-side layout for the batch-written gold tables** (section 7).
- **`fact_lineitem`'s `ORDER BY` and `proj_supplier`**, the most contestable choice in the layout, tested by the B1 sweep.
- **The P3 read pattern**: `FINAL` against the `argMax` latest-version idiom, benchmarked for correctness and measured for latency.
- **A discrepancy between two closed tickets, recorded rather than silently resolved.** [the serving layer](serving-layer.md) section 11 says the B1 sweep "test[s] the Iceberg-side partition transform and sort order"; [the benchmark plan](benchmark-plan.md) section 4 defines B1's three variants as ClickHouse partition and `ORDER BY` values. Either the sweep varies the Iceberg side too, in which case the benchmark plan's variant table is missing that column, or the serving layer's sentence overstates what B1 varies. The synthesis does not pick one; it is named here so the two documents are reconciled before B1 runs.

---

*Resolved by [the architecture-synthesis ticket](https://github.com/SoongGuanLeong/de-platform/issues/26) on [the map](https://github.com/SoongGuanLeong/de-platform/issues/9). Inputs: [dataset-selection](dataset-selection.md), [serving-layer](serving-layer.md), [streaming-jobs](streaming-jobs.md), [governance-and-data-quality](governance-and-data-quality.md), [data-contracts](data-contracts.md), [benchmark-plan](benchmark-plan.md), and [the system architecture](system-architecture.md) and [the data-flow diagrams](data-flow.md) written beside this document.*
