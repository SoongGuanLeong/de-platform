# The serving layer's concrete shape: layout, personas and the query set

**Ticket:** [The serving layer's concrete shape: layout, personas and the query set](https://github.com/SoongGuanLeong/de-platform/issues/12)
**Map:** [Vendor-neutral lakehouse data platform: architecture proposal](https://github.com/SoongGuanLeong/de-platform/issues/9)
**Target posting:** ONL Biz Solutions, Senior Data Engineer - Data Lakehouse ([JobStreet 94703893](https://my.jobstreet.com/job/94703893)), cached verbatim at `~/projects/career-ops/data/jd-cache/031.md`.
**Decisions recorded here:** [ADR-0012](adr/0012-flink-writes-the-serving-copy.md), resting on [ADR-0003](adr/0003-materialised-serving-store-not-read-through.md) and [ADR-0008](adr/0008-two-spines-with-no-cross-domain-join.md).

---

## 1. What this document is

The concrete shape of the serving layer: the analyst personas and their query set, the gold grain, which tables get a ClickHouse copy, how those copies are kept current, and the physical layout each one carries. It resolves [the serving-layer ticket](https://github.com/SoongGuanLeong/de-platform/issues/12) on the map, and it is the per-table detail that [the technology-selection ticket](https://github.com/SoongGuanLeong/de-platform/issues/8) deliberately left open.

It is a design, not a result. Nothing here has been measured, and no latency, row count, file count or storage figure appears. Every layout choice is a baseline for the benchmark plan to test, and the comparison that motivates the architecture is specified in section 8 and run later.

**The claim is scoped to the nine named queries in section 3.** The layout is not asserted to be optimal in general. It is the shape chosen to serve that workload, each choice carrying a reason, and where a choice is genuinely contestable it is named as an experiment rather than settled.

## 2. The three analyst personas

M9 requires three named personas with their real questions and a latency budget each. Two constraints shape the choice. No persona's question may cross the two spines, because nothing joins them ([ADR-0008](adr/0008-two-spines-with-no-cross-domain-join.md)). And the three together must exercise batch analytics, the near-real-time CDC path, and the network spine's spatial and SCD2 joins, or the query set never reaches the layout decisions this document exists to make.

| Persona | Spine and path | Representative questions | Latency class |
|---|---|---|---|
| **The commercial analyst** | Commerce, TPC-H, batch | Revenue by nation and part category for the last complete quarter, and which suppliers drove it; which parts have more than one supplier and what the price spread is | interactive |
| **The network analyst** | Network, RIPE Atlas joined to ONSPD, batch over the capture | Which UK postcode areas have the worst median round-trip time this week; how many probes resolve to a terminated postcode; how connectivity moved across the capture | dashboard |
| **The operations analyst** | Commerce, TPC-C CDC, streaming | Orders in flight by warehouse right now; items below the reorder threshold; orders past their delivery window | near-real-time |

The operations analyst is the only persona that requires a streaming serving feed, and is therefore the business justification for the single named streaming exception in section 5. The other two are served from batch.

## 3. The nine-query benchmark set

The query set is the input to the layout, so it is fixed and finite before any layout choice is made. Nine queries, three per persona, each chosen because it exercises a distinct physical-layout problem rather than because it is representative. The set is the workload both arms of section 8 are measured on. It is not expanded unless a requirement is uncovered that it cannot evidence.

| ID | Persona | Question | What it exercises |
|---|---|---|---|
| **C1** | Commercial | Revenue by nation and part category for the last complete quarter | Line grain; joins up to customer and nation and across to part; column pruning and a large aggregation |
| **C2** | Commercial | Top 10 suppliers by revenue contribution | The fan-out demonstration in section 4; join-path correctness against the `partsupp` trap |
| **C3** | Commercial | Parts with more than one supplier and the price spread across them | Aggregation over the `PARTSUPP` many-to-many bridge |
| **N1** | Network | Median round-trip time by postcode area for the capture window | Result grain to probe, then the spatial join to postcode and area; a high-cardinality aggregation |
| **N2** | Network | Probes whose nearest postcode has been terminated | SCD2 point-in-time lookup joined to the spatial lookup |
| **N3** | Network | Connectivity trend by postcode area across the capture | A time-bucketed aggregation, which is what the rollup in section 7 serves |
| **O1** | Operations | Orders in flight by warehouse right now | Order-line grain filtered to undelivered; the freshness-sensitive query |
| **O2** | Operations | Stock-out risk by warehouse | `fact_stock` at (warehouse, item) grain; a state aggregate |
| **O3** | Operations | Orders past their delivery window | `fact_delivery` grain; depends on the `NEW_ORDER` delete events landing |

## 4. The gold grain per table, and the fan-out demonstration

Grain is what one row represents. It is the decision most star schemas get wrong, and M6 asks for one query where the correct grain is the whole point, shown beside the version that gets it wrong.

**Commerce, TPC-H.** `fact_lineitem` at line grain, one row per order line, which is the atomic revenue grain. Dimensions `dim_customer_tpch`, `dim_part`, `dim_supplier`, `dim_nation`, `dim_region`, `dim_date`. The customer dimension is suffixed by source because TPC-C also has a CUSTOMER table, so an unsuffixed `dim_customer` would be ambiguous in a `commerce` namespace shared by both sources. There is deliberately no `fact_orders` at order grain, because order-grain and line-grain measures sitting side by side is exactly the trap C2 exists to expose.

**Commerce, TPC-C.** `fact_order_line` at order-line grain, with the order header denormalised onto it; `fact_stock` at (warehouse, item) grain; `fact_delivery` at order grain. Dimensions warehouse, district, customer and item; the customer dimension is silver-only (PII, per the governance document), so no TPC-C gold dimension table is created and the name `dim_customer_tpcc` is reserved rather than used.

**Network, RIPE Atlas.** `fact_measurement_result` at result grain; `dim_probe`; `dim_measurement`.

**Network, ONSPD.** `dim_postcode` as SCD2, with `valid_from` and `valid_to` derived from `DOINTR` and `DOTERM` and null meaning live. The postcode-to-geography relationship is a bridge table, not a straight join, because one postcode maps to several administrative, health and census geographies at once in the boundary-straddling cases.

### The fan-out demonstration (M6)

The correct query sums at line grain and joins the supplier on the line's own supplier key, which is one supplier per line:

```sql
SELECT s_suppkey, s_name, sum(l_extendedprice * (1 - l_discount)) AS revenue
FROM lineitem
JOIN supplier ON l_suppkey = s_suppkey
WHERE l_shipdate >= DATE '1995-01-01' AND l_shipdate < DATE '1995-04-01'
GROUP BY s_suppkey, s_name
ORDER BY revenue DESC
LIMIT 10;
```

The trap reaches the supplier through `partsupp` and joins on the part key alone:

```sql
SELECT s_suppkey, sum(l_extendedprice * (1 - l_discount)) AS revenue
FROM lineitem
JOIN partsupp ON l_partkey = ps_partkey          -- the missing ps_suppkey is the bug
JOIN supplier ON ps_suppkey = s_suppkey
GROUP BY s_suppkey
ORDER BY revenue DESC
LIMIT 10;
```

Every line is multiplied by the number of suppliers that part has, so revenue is silently inflated. TPC-H publishes the expected answers, so the error is detectable against an oracle rather than merely arguable, which is what makes this a demonstration and not an assertion.

## 5. The serving-table inventory and the batch/streaming split

ADR-0003 fixes the architecture: ClickHouse holds MergeTree copies and catalog read-through is retained only as the comparison arm. The open decisions are therefore which gold tables get a copy, and how each is refreshed. Technology-selection position 2 set the rule, batch by default and streaming for named exceptions.

- **Batch-materialised by Spark:** the TPC-H star for the commercial analyst, and the network tables for the network analyst. Both spines' sources are static or replayed, so batch is authoritative and idempotent.
- **Streaming-materialised by Flink:** `fact_order_line`, `fact_stock` and `fact_delivery` for the operations analyst. This is the single named streaming exception, and the operations analyst is its justification.
- **Iceberg-only:** everything not required by the serving workload. Bronze and silver have no serving copy.

## 6. The incremental materialisation mechanism

The constraint that decides it is already recorded in [the salvage list](salvage-list.md): Iceberg's incremental reader is append-only, so a table maintained by `MERGE` cannot be consumed incrementally. That rules out "read the rows added since last time" for every gold table, because the gold tables are `MERGE`-maintained.

**Batch arm: partition-scoped rebuild with an atomic swap.** Spark reads the affected Iceberg partitions, writes them into a staging MergeTree table with an identical schema, then `ALTER TABLE ... REPLACE PARTITION` swaps it in atomically. A reader sees the old partition or the new one, never a gap and never a duplicate, and re-running is idempotent because the staging table is rebuilt from scratch. This is the ClickHouse-side twin of the `MERGE ... WHEN NOT MATCHED BY SOURCE THEN DELETE` pattern already adopted for Iceberg gold.

**Streaming arm: key-based replacement into a `ReplacingMergeTree`, versioned by the source LSN.** MergeTree has no in-place update, so an upsert here means "insert the new version of the row and let the engine collapse the duplicates on merge, keeping the highest version." Key it on the TPC-C business key and use the LSN that every event already carries (M2) as the version column, so last-write-wins is deterministic and matches the Iceberg sink's semantics. Deletes, such as the `NEW_ORDER` rows Delivery removes, are carried as tombstones with a soft-delete flag, so a replayed delete converges instead of resurrecting the row.

**Why the CDC tables cannot use partition swap.** A late update can touch an arbitrarily old partition, so there is no bounded set of partitions to rebuild. That is the property that makes them the streaming exception, and it is the same property that made the Iceberg incremental reader unusable for `MERGE`-maintained tables.

**The M8 mechanism is Flink writing ClickHouse, not the ClickHouse Kafka engine** ([ADR-0012](adr/0012-flink-writes-the-serving-copy.md)). The official ClickHouse Flink connector's sink is at-least-once, so convergence is carried by deterministic LSN versioning in the table engine rather than by the connector.

## 7. The physical layout

The baseline, with the reason for each choice. `PRIMARY KEY` stays equal to `ORDER BY`, the ClickHouse default, so the declaration matches `system.tables.sorting_key` and `system.tables.primary_key`, which [the completion bar](completion-bar.md) checks.

| Table | Engine | Partition | `ORDER BY` | Codecs | TTL | Projection |
|---|---|---|---|---|---|---|
| `fact_lineitem` (P1) | MergeTree | `toYYYYMM(l_shipdate)` | `(l_shipdate, l_partkey, l_suppkey)` | Delta on dates, ZSTD on decimals and strings, LowCardinality on flags | none | `proj_supplier` on `(l_suppkey, l_shipdate)` |
| `dim_customer_tpch`, `dim_part`, `dim_supplier` (P1) | MergeTree | none | business key | LowCardinality, ZSTD | none | none |
| `dim_nation`, `dim_region`, `dim_date` (P1) | MergeTree | none | key | LowCardinality | none | none |
| `fact_measurement_area` (P2) | MergeTree | `toStartOfHour(ts)` | `(ts, postcode_area, probe_id)` | DoubleDelta on `ts`, Gorilla on RTT, LowCardinality on area and ASN | `ts + 90 days` | none |
| `measurement_hourly_by_area` (P2) | AggregatingMergeTree via materialised view | `toYYYYMM(hour)` | `(postcode_area, hour)` | LowCardinality, ZSTD | none | n/a |
| `dim_postcode` (P2) | MergeTree | none | `(postcode, valid_from)` | LowCardinality on the roughly 20 geography columns, ZSTD | none | none |
| `postcode_geography` (P2) | MergeTree | none | `(postcode, geography_type, geography_code)` | LowCardinality | none | none |
| `fact_order_line` (P3) | ReplacingMergeTree(`lsn`) | `toYYYYMM(o_entry_d)` | `(w_id, d_id, o_id, ol_number)` | LowCardinality, ZSTD, Delta on dates | 365 days | none |
| `fact_stock` (P3) | ReplacingMergeTree(`lsn`) | none | `(s_w_id, s_i_id)` | LowCardinality, ZSTD | none | none |
| `fact_delivery` (P3) | ReplacingMergeTree(`lsn`) | `toYYYYMM(o_entry_d)` | `(w_id, d_id, o_id)` | LowCardinality, ZSTD | none | none |

### The shape of each serving table

- **P1 commerce is a straight copy.** C1 to C3 are star joins over `lineitem` and its dimensions, so the fact and dimensions are served as they are. Denormalising would hide the `LINEITEM` to `PARTSUPP` fan-out that C2 exists to expose, and the star join is the pattern an analyst expects to see.
- **P2 network is a shaped copy plus a rollup.** N1 and N3 need result, then probe, then postcode, then area, a chain that is expensive and needed by every query. The resolved `postcode_area` is therefore baked onto `fact_measurement_area` at materialisation time and the serving query becomes a plain aggregation. N3 is a different grain again, so it is served by the `measurement_hourly_by_area` rollup rather than by rescanning raw results. N2 still needs the SCD2 termination state, so `dim_postcode` stays normalised and the fact records the postcode and the as-of date it was resolved against.
- **P3 commerce CDC is a straight copy.** O1 to O3 are simple aggregates over live state, so the three `ReplacingMergeTree` facts stand alone.

### The reasons that matter

- **Partition granularity.** Month for the year-spanning tables, which is roughly 84 partitions for TPC-H and healthy; hour for the 24-hour measurement capture, so N3's time buckets prune; none for dimensions and `fact_stock`, because partitioning a small table only creates tiny parts.
- **`ORDER BY` leading column.** `l_shipdate` first because every P1 query has a date predicate, and `ts` first for the measurement fact for the same reason. The trailing columns follow the join and grouping keys. This is the most contestable choice in the table, and `fact_lineitem`'s order is named in section 11 as an experiment.
- **TTL.** None on the TPC-H fixture, because it is a fixed historical set whose published answers are the test oracle and deleting rows would destroy the oracle. Retention is demonstrated where data genuinely ages.
- **Projections.** Exactly one, `proj_supplier` on `fact_lineitem`, because C2 is a genuinely different access path, grouping by supplier rather than filtering by date. Every other table starts with none, and a projection is added only if a measured p95 misses its budget.

### The TTL rationale

The 365-day TTL on the two CDC facts is a serving-window decision, not a data-retention decision. TPC-C is a live OLTP mirror whose operational questions (O1 to O3) ask about current state, so a bounded one-year serving window is the operational-detail policy for that data class; Iceberg remains the record and holds the full history, and the reconciliation in M2 compares source against Iceberg rather than against ClickHouse. The measurement fact keeps 90 days for the same reason at a different cadence: its capture is a fixed window and the hourly rollup carries the longer trend, so raw results need only the recent serving window. The TPC-H fixture carries no TTL at all, because it is a static oracle rather than aging production data. This is where M12's "expired rows gone and in-window rows survived" assertion is cheapest to demonstrate.

## 8. The two-arm comparison

The read-through arm is ClickHouse's `DataLakeCatalog` database engine with `catalog_type = 'rest'` pointed at Polaris. It reads table metadata through the catalog and the Parquet data files directly from SeaweedFS. It is Beta, it is read-only, and it is not a MergeTree table, so it has no `ORDER BY`, no projections, no codecs and no TTL. That absence is the point of the arm.

- **Queries:** the six P1 and P2 queries, C1 to C3 and N1 to N3, on both arms.
- **Profile:** `batch`, at a stated volume and concurrency, against the same pinned Iceberg snapshot.
- **Primary metric:** p50 and p95 latency per query. **Supporting:** rows read and bytes read per query, and whether each query is servable on the read-through arm at all, since some may need rewriting for the catalog path.
- **Controls, declared with the result:** the ClickHouse pin, the Polaris pin, the Iceberg snapshot id, the exact query text, the concurrency, and the metadata-cache settings.
- **Metadata-cache handling:** the read-through arm is measured with its documented best-practice settings, the metadata cache and `iceberg_metadata_staleness_ms` on, because measuring it uncached would be a strawman. One uncached run is recorded as well, so the catalog-fetch cost is visible and the delta can be attributed to layout rather than to a metadata round trip.
- **Data-correctness control:** assert both arms return identical result sets for the same snapshot.
- **The hypothesis:** that the materialised arm is faster. This is the thing the experiment establishes, not a premise it assumes. If it holds, the delta is the recorded justification for ADR-0003 and converts the architecture choice from a preference into a measurement.
- **Honest limit:** the read-through arm is Beta and read-only, so this is a latency comparison on the batch tables, not evidence that read-through is a viable serving architecture.

The freshness trade is measured separately, never mixed into the latency delta. The read-through arm is fresher because it reads the current Iceberg snapshot, and the materialised copy lags by the streaming feed; M8 measures that lag end to end, from the source commit timestamp to the row being visible in the ClickHouse copy, p50 and p99, with the same measurement recorded on the read-through arm as the baseline. P3 is excluded from the latency comparison for exactly this reason.

## 9. The budget position

Each persona's latency class is fixed now as a design constraint, because the layout has to satisfy it:

| Persona | Class | Shape of the commitment |
|---|---|---|
| Commercial analyst | interactive | p50 and p95 on the six batch queries |
| Network analyst | dashboard | p50 and p95 on the six batch queries |
| Operations analyst | near-real-time | query p95, plus the freshness p99 from section 8 |

The per-query numbers are **not** declared here. They are committed in `docs/budgets.yaml` before the benchmark runs, with the commit that introduced each one, because a per-query threshold invented before the workload is measured on this hardware would be a guess wearing a threshold's clothes. A budget changed later creates a new entry and invalidates the evidence that cited the old one.

## 10. Named constraints

1. **No cross-domain join.** Nothing joins the commerce spine to the network spine; the only cross-spine link is time (ADR-0008).
2. **No conformed geography dimension across the platform.** Geography is a network-spine concept only.
3. **The layout claim is scoped to the nine queries.** It is the shape chosen to serve C1 to C3, N1 to N3 and O1 to O3, not a universal optimum.
4. **Nothing here is measured.** Every partition, key, codec, TTL and projection is a baseline to be tested.
5. **The materialised arm being faster is a hypothesis.** The comparison in section 8 tests it.
6. **P3 is excluded from the latency comparison** and used only for the freshness measurement, so the two effects never confound each other.
7. **The streaming serving copy is at-least-once.** Convergence comes from deterministic LSN versioning in `ReplacingMergeTree`, not from the connector.

## 11. Open measurements

- **`fact_lineitem` ordering and projection.** The `ORDER BY` and `proj_supplier` are workload-driven hypotheses. M5's three layout variants of one hot table test the Iceberg-side partition transform and sort order, measured partly through ClickHouse p50/p95, and a changed Iceberg layout means re-materialising the ClickHouse copy.
- **The P3 read pattern.** `FINAL` and the `argMax`/`GROUP BY` latest-version idiom are both benchmarked for correctness and measured latency, and the winner becomes the declared pattern for O1 to O3. `ReplacingMergeTree` supports either, so the layout does not constrain the outcome.
- **The per-query budgets.** Committed in `docs/budgets.yaml` before the benchmark, per section 9.
- **The two-arm delta.** Measured per section 8, and the magnitude is unknown until then.

---

*Resolved by [the serving-layer ticket](https://github.com/SoongGuanLeong/de-platform/issues/12) on [the map](https://github.com/SoongGuanLeong/de-platform/issues/9). Inputs: [`docs/dataset-selection.md`](dataset-selection.md), [`docs/requirements-matrix.md`](requirements-matrix.md), [`docs/technology-selection.md`](technology-selection.md), [`docs/completion-bar.md`](completion-bar.md), [`docs/salvage-list.md`](salvage-list.md).*
